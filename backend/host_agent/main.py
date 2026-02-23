"""Host agent main entry point."""

import logging
import os
import traceback
from typing import Dict, Any, Optional
from pprint import pformat

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.events import Event, EventActions
from google.adk.memory import InMemoryMemoryService
from google.genai import types

from backend.host_agent.routing_agent import get_root_agent_async, AuthRequiredError
from backend.common.jwt_auth import create_access_token, verify_token


# =========================
# App / Agent Setup
# =========================

APP_NAME = "routing_app"
SESSION_SERVICE = InMemorySessionService()
MEMORY_SERVICE = InMemoryMemoryService()

# Bank server configuration
BANK_URL = os.getenv('BANK_URL', 'http://localhost:8006')

# ============= FASTAPI APP =============
app = FastAPI(
    title="Host Agent HTTP Bridge",
    description="HTTP bridge to A2A host agent",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
security = HTTPBearer()

# =========================
# Models
# =========================

class ChatMessage(BaseModel):
    message: str
    media_base64: Optional[str] = None
    media_mime: Optional[str] = None
    media_name: Optional[str] = None
    media_kind: Optional[str] = None
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    status: str = "completed"

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str


# =========================
# Helpers
# =========================

async def bank_authenticate(username: str, password: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BANK_URL}/user_auth/authenticate",
                json={"username": username, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("user_id")
            return None
    except Exception as e:
        print(f"[ERROR] bank authentication: {e}")
        return None

async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False))
) -> Dict[str, Any] | None:
    if not credentials:
        return None
    try:
        token = credentials.credentials
        return verify_token(token)
    except Exception as e:
        print(f"[WARN] Invalid token in optional auth: {e}")
        return None

async def process_agent_events(event_iterator) -> str:
    response_text = ""
    async for event in event_iterator:
        if event.is_final_response():
            if event.content and event.content.parts:
                final_text = "".join([p.text for p in event.content.parts if p.text]).strip()
                if final_text:
                    response_text = final_text
                    break
        else:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text and part.text.strip():
                        response_text += part.text.strip() + " "
                    elif hasattr(part, "function_response") and part.function_response:
                        func_response = part.function_response
                        if hasattr(func_response, "response") and func_response.response:
                            result = func_response.response.get("result", "")
                            if result and isinstance(result, str):
                                if not response_text or response_text.strip() == "":
                                    response_text = result
    return response_text


# =========================
# Guardrails Integration
# =========================
GUARDRAILS_URL = os.getenv('GUARDRAILS_URL', 'http://localhost:8005')

async def check_guardrails_input(message: str) -> bool:
    """Check user input against Guardrails service."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{GUARDRAILS_URL}/check_input",
                json={"message": message}
            )
            if response.status_code == 200:
                data = response.json()
                if not data.get("is_safe", True):
                    print(f"[GUARDRAILS] Input blocked: {data.get('reason')}")
                    return False
    except Exception as e:
        print(f"[ERROR] Guardrails input check failed: {e}")
    # Default open if service unreachable/errors
    return True

async def check_guardrails_output(message: str) -> tuple[bool, str | None]:
    """Check agent output against Guardrails service."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{GUARDRAILS_URL}/check_output",
                json={"message": message}
            )
            if response.status_code == 200:
                data = response.json()
                is_safe = data.get("is_safe", True)
                filtered = data.get("filtered_message")
                if not is_safe:
                    print(f"[GUARDRAILS] Output blocked/filtered: {data.get('reason')}")
                return is_safe, filtered
    except Exception as e:
        print(f"[ERROR] Guardrails output check failed: {e}")
    # Default open
    return True, message


# =========================
# API Endpoint
# =========================

@app.post("/login", response_model=LoginResponse, tags=["login"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user_id = await bank_authenticate(form_data.username, form_data.password)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    access_token = create_access_token(user_id=user_id)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user_id,
        username=form_data.username
    )

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_endpoint(
    chat_message: ChatMessage,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
):
    try:
        # 1. Guardrails Check Input
        is_safe_input = await check_guardrails_input(chat_message.message)
        if not is_safe_input:
            return ChatResponse(
                response="I'm sorry, I cannot process your request due to policy restrictions.",
                status="completed"
            )

        if current_user:
            user_id = str(current_user.get("user_id", "default_user"))
            jwt_token = credentials.credentials if credentials else None
        else:
            user_id = "guest_user" 
            jwt_token = None

        session_id = chat_message.session_id if chat_message.session_id else f"session_{user_id}"

        session = await SESSION_SERVICE.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

        current_request_state = {
            "jwt_token": jwt_token,
            "user_id": user_id,
        }
        
        if not session:
            print(f"Creating new session with state: {current_request_state}")
            session = await SESSION_SERVICE.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
                state=current_request_state or {},
            )
        else:
            try:
                actions = EventActions(state_delta=current_request_state)
                event = Event(
                    invocation_id="http_bridge_state_update",
                    author="host_agent_http",
                    actions=actions,
                )
                await SESSION_SERVICE.append_event(session, event)
            except Exception as exc:
                print(f"[HTTP-DEBUG] Failed to append session state: {exc}")

        routing_agent = await get_root_agent_async()
        runner = Runner(
            agent=routing_agent,
            app_name=APP_NAME,
            session_service=SESSION_SERVICE,
            memory_service=MEMORY_SERVICE,
        )

        try:
            event_iterator = runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=chat_message.message)]),
            )
            response_text = await process_agent_events(event_iterator)
            
            # 2. Guardrails Check Output
            is_safe_output, filtered_responseText = await check_guardrails_output(response_text)
            final_response = filtered_responseText if is_safe_output and filtered_responseText else "Response blocked by policy rules."

            return ChatResponse(response=final_response or "No response generated", status="completed")
        except AuthRequiredError:
            print("DEBUG: AuthRequiredError caught in chat_endpoint. Returning [AUTH_REQUIRED]")
            return ChatResponse(response="[AUTH_REQUIRED]")
            
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def main():
    print("[START] Starting Host Agent main entry point...")
    uvicorn.run(
        "backend.host_agent.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

if __name__ == "__main__":
    main()

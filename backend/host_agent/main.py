"""Host agent main entry point."""

import os
import traceback
from pprint import pformat
from typing import Dict, Any, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.events import Event, EventActions
from google.adk.memory import InMemoryMemoryService
from google.genai import types

import backend.host_agent.routing_agent as routing_agent_module

from backend.common.jwt_auth import create_access_token, verify_token
from observability import get_logger, setup_telemetry, instrument_app, setup_logging

logger = get_logger(__name__)

# Initialize OpenTelemetry tracing (reads from OTEL_* environment variables)
setup_telemetry()

# Initialize centralized logging (reads from LOG_* environment variables)
setup_logging()


# =========================
# App / Agent Setup
# =========================

APP_NAME = "routing_app"

SESSION_SERVICE = InMemorySessionService()
MEMORY_SERVICE = InMemoryMemoryService()

# Bank server configuration
BANK_URL = os.getenv("BANK_URL", "http://localhost:8006")

# Guardrails service configuration
GUARDRAILS_URL = os.getenv("GUARDRAILS_URL", "http://localhost:8005")

# Defaults (reference-style)
DEFAULT_USER_ID = "default_user"
DEFAULT_SESSION_ID = "default_session"

# Global runner (reference-style)
ROUTING_AGENT_RUNNER: Runner | None = None

# ============= FASTAPI APP =============
app = FastAPI(title="Host Agent HTTP Bridge")
instrument_app(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# =========================
# Request/Response Models
# =========================

class ChatRequest(BaseModel):
    message: str
    media_base64: Optional[str] = None
    media_mime: Optional[str] = None
    media_name: Optional[str] = None
    media_kind: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    status: str = "completed"


class LoginRequest(BaseModel):
    username: str
    password: str


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
                json={"username": username, "password": password},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("user_id")
            return None
    except Exception as e:
        logger.exception(f"[ERROR] bank authentication: {e}")
        return None


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Dict[str, Any] | None:
    if not credentials:
        return None
    try:
        return verify_token(credentials.credentials)
    except Exception as e:
        logger.warning(f"[WARN] Invalid token in optional auth: {e}")
        return None


async def check_guardrails_input(message: str) -> bool:
    """Check user input against Guardrails service."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{GUARDRAILS_URL}/check_input",
                json={"message": message},
            )
            if response.status_code == 200:
                data = response.json()
                if not data.get("is_safe", True):
                    logger.warning(f"[GUARDRAILS] Input blocked: {data.get('reason')}")
                    return False
    except Exception as e:
        logger.error(f"[ERROR] Guardrails input check failed: {e}")
    return True


async def check_guardrails_output(message: str) -> tuple[bool, str | None]:
    """Check agent output against Guardrails service."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{GUARDRAILS_URL}/check_output",
                json={"message": message},
            )
            if response.status_code == 200:
                data = response.json()
                is_safe = data.get("is_safe", True)
                filtered = data.get("filtered_message")
                if not is_safe:
                    logger.warning(
                        f"[GUARDRAILS] Output blocked/filtered: {data.get('reason')}"
                    )
                return is_safe, filtered
    except Exception as e:
        logger.error(f"[ERROR] Guardrails output check failed: {e}")
    return True, message


async def get_response_from_agent(message: str, user_id: str, session_id: str) -> str:
    """
    Use the global Runner, log tool calls, return only final response text.
    Also consumes full stream (no early break) to avoid GeneratorExit issues.
    """
    if ROUTING_AGENT_RUNNER is None:
        return "Error: Agent not initialized yet. Please wait for startup to complete."

    try:
        event_iterator = ROUTING_AGENT_RUNNER.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
        )

        final_response_text = ""
        async for event in event_iterator:
            # Log tool calls and responses to console (not sent to frontend)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "function_call", None):
                        logger.info(f"\nTool Call: {part.function_call.name}")
                        logger.debug(
                            pformat(
                                part.function_call.model_dump(exclude_none=True),
                                indent=2,
                                width=80,
                            )
                        )
                    elif getattr(part, "function_response", None):
                        response_content = part.function_response.response
                        if isinstance(response_content, dict) and "response" in response_content:
                            formatted = response_content["response"]
                        else:
                            formatted = response_content
                        logger.info(f"\nTool Response from {part.function_response.name}")
                        logger.debug(pformat(formatted, indent=2, width=80))

            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = "".join(
                        [p.text for p in event.content.parts if getattr(p, "text", None)]
                    ).strip()
                elif event.actions and getattr(event.actions, "escalate", None):
                    final_response_text = (
                        f"Agent escalated: {getattr(event, 'error_message', None) or 'No specific message.'}"
                    )
                # DON'T break; consume rest of stream (reference behavior)

        return final_response_text if final_response_text else "No response from agent."

    except Exception as e:
        logger.info(f"Error in get_response_from_agent (Type: {type(e)}): {e}")
        traceback.print_exc()
        return f"An error occurred while processing your request: {str(e)}"


# =========================
# API Endpoints
# =========================

@app.post("/login", response_model=LoginResponse, tags=["login"])
async def login_endpoint(request: LoginRequest):
    user_id = await bank_authenticate(request.username, request.password)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication failed")

    # keep your existing token create method
    access_token = create_access_token(user_id=user_id)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user_id,
        username=request.username,
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_endpoint(
    request: ChatRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
):
    try:
        # 1) Guardrails input
        is_safe_input = await check_guardrails_input(request.message)
        if not is_safe_input:
            return ChatResponse(
                response="I'm sorry, I cannot process your request due to policy restrictions.",
                status="completed",
            )

        # 2) Determine user/session
        if current_user:
            user_id = str(current_user.get("user_id", DEFAULT_USER_ID))
            jwt_token = credentials.credentials if credentials else None
        else:
            user_id = "guest_user"
            jwt_token = None

        session_id = request.session_id or f"session_{user_id}"

        # 3) Create/update ADK session state
        session = await SESSION_SERVICE.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

        # IMPORTANT: routing_agent.send_message reads state["user_jwt"]
        current_request_state = {
            "user_id": user_id,
            "user_jwt": jwt_token,
        }

        if not session:
            logger.info(f"Creating new session with state: {current_request_state}")
            await SESSION_SERVICE.create_session(
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
                logger.warning(f"[HTTP-DEBUG] Failed to append session state: {exc}")

        # 4) just call get_response_from_agent (global runner)
        response_text = await get_response_from_agent(
            request.message, user_id=user_id, session_id=session_id
        )

        # 5) Guardrails output
        is_safe_output, filtered = await check_guardrails_output(response_text)
        final_response = (
            filtered if (is_safe_output and filtered is not None) else "Response blocked by policy rules."
        )

        return ChatResponse(response=final_response or "No response generated", status="completed")

    except Exception as e:
        logger.exception(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================
# Startup Hook (reference pattern)
# =========================

@app.on_event("startup")
async def startup_event():
    global ROUTING_AGENT_RUNNER

    logger.info("Initializing Routing Agent...")
    # IMPORTANT: this matches your NEW routing_agent.py API (init_routing_agent + root_agent)
    await routing_agent_module.init_routing_agent()

    logger.info("Creating ADK session...")
    await SESSION_SERVICE.create_session(
        app_name=APP_NAME,
        user_id=DEFAULT_USER_ID,
        session_id=DEFAULT_SESSION_ID,
    )

    logger.info("Initializing Runner...")
    ROUTING_AGENT_RUNNER = Runner(
        agent=routing_agent_module.root_agent,  # initialized by init_routing_agent()
        app_name=APP_NAME,
        session_service=SESSION_SERVICE,
        memory_service=MEMORY_SERVICE,
    )

    logger.info("Startup complete.")


def main():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
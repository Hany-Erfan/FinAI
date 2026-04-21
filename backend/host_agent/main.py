"""Host agent main entry point."""

import os
import time
import traceback
from pprint import pformat
import secrets
import traceback
from typing import Optional
import httpx
from backend.common.masking_pii import DataMasker
from backend.postgres_db.database import get_db, init_db
from backend.postgres_db.models import MessageRole
from backend.postgres_db.repository import SessionRepository
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request, Response, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.events import Event, EventActions
from google.adk.memory import InMemoryMemoryService
from google.genai import types

from backend.bank_server.utils.security_deps import auth_cookie_name, csrf_cookie_name, get_current_user, refresh_session_cookies, verify_csrf
from backend.host_agent.routes.admin_analytics import router as admin_analytics_router
from backend.host_agent.routes.admin_sessions import router as admin_sessions_router
from backend.bank_server.utils.user_store import get_user_by_username
from backend.common.pass_auth import verify_password
import backend.host_agent.routing_agent as routing_agent_module
from backend.host_agent.utils import Language
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

# Voice service configuration
VOICE_SERVICE_URL = os.getenv("VOICE_SERVICE_URL", "http://localhost:8008")

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
    allow_origins=["*", "http://localhost:5173", "http://127.0.0.1:5173"], # for local setup
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_sessions_router)
app.include_router(admin_analytics_router)

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

class VoiceChatResponse(BaseModel):
    user_message: str
    response: str
    audio_base64: Optional[str] = None
    status: str = "completed"

class LoginRequest(BaseModel):
    username: str
    password: str
    session_id: str

class LoginResponse(BaseModel):
    user_id: str
    message: str
    role: str
    username: str

class User(BaseModel):
    username: str
    role: str
    full_name: str
    user_id: str

# =========================
# Helpers
# =========================

async def check_guardrails_input(message: str) -> tuple[bool, str | None]:
    """Check user input against Guardrails service."""
    # try:
    #     timeout = httpx.Timeout(30.0, connect=5.0)  # allow LLM-based validators time to finish
    #     async with httpx.AsyncClient(timeout=timeout) as client:
    #         response = await client.post(
    #             f"{GUARDRAILS_URL}/check_input",
    #             json={"message": message},
    #         )
    #         if response.status_code == 200:
    #             data = response.json()
    #             if not data.get("is_safe", True):
    #                 reason = data.get("reason")
    #                 logger.warning(f"[GUARDRAILS] Input blocked: {reason}")
    #                 return False, reason
    #             return True, None
    # 
    #         logger.error(f"[ERROR] Guardrails input check non-200: {response.status_code} body={response.text!r}")
    #         return False, "Validation service unavailable."  # fail closed
    # 
    # except Exception as e:
    #     logger.error(f"[ERROR] Guardrails input check failed: {type(e).__name__}: {e!r}")
    #     return False, "Validation service error."  # fail closed
    return True, None


async def check_guardrails_output(message: str) -> tuple[bool, str | None, str | None]:
    """Check agent output against Guardrails service."""
    # try:
    #     async with httpx.AsyncClient(timeout=5.0) as client:
    #         response = await client.post(
    #             f"{GUARDRAILS_URL}/check_output",
    #             json={"message": message},
    #         )
    #         if response.status_code == 200:
    #             data = response.json()
    #             is_safe = data.get("is_safe", True)
    #             filtered = data.get("filtered_message")
    #             reason = data.get("reason")
    #             if not is_safe:
    #                 logger.warning(
    #                     f"[GUARDRAILS] Output blocked/filtered: {reason}"
    #                 )
    #             return is_safe, filtered, reason
    # except Exception as e:
    #     logger.error(f"[ERROR] Guardrails output check failed: {e}")
    return True, message, None


def log_tool_calls_and_responses(event) -> None:
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
            log_tool_calls_and_responses(event)

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

def get_chat_respository(db = Depends(get_db)) -> SessionRepository:
    return SessionRepository(db = db, masker= DataMasker())

def detect_language(text: str) -> str:
    # Lightweight script-based detection (Arabic vs default English)
    # Arabic Unicode blocks: \u0600-\u06FF, \u0750-\u077F, \u08A0-\u08FF
    for ch in text:
        o = ord(ch)
        if (0x0600 <= o <= 0x06FF) or (0x0750 <= o <= 0x077F) or (0x08A0 <= o <= 0x08FF):
            return "ar"
    return "en"

def build_transcript(messages) -> str:
    lines = []
    for m in messages:
        role_label = m.role.value.upper()
        lines.append(f"[{role_label}]: {m.content}")
    return "\n".join(lines)

# =========================
# API Endpoints
# =========================

@app.post("/login", response_model=LoginResponse, tags=["login"])
def login(payload: LoginRequest, response: Response, repo = Depends(get_chat_respository)) -> LoginResponse:
    if not payload.session_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session id required")

    user = get_user_by_username(payload.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(payload.password, user["password_hash"], user["salt"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    csrf_token = secrets.token_urlsafe(32)
    refresh_session_cookies(response, user, payload.session_id, csrf_token)

    # init session
    repo.create_session(
            user_id=user["user_id"],
            user_name=payload.username,
            session_id=payload.session_id,
        )
    logger.info(f"session with id '{payload.session_id}' has started")

    return LoginResponse(
        message="Login successful",
        role=user["role"],
        username=user["username"],
        user_id=user["user_id"]
    )


@app.get("/currentUser", response_model=User , tags=["User"])
def getCurrentUser(current_user=Depends(get_current_user)) -> User:
    return User(
        user_id=current_user["user_id"],
        username=current_user["username"],
        role=current_user["role"],
        full_name=current_user["full_name"],
)


@app.post("/logout", tags=["Logout"])
def logout(
    request: Request,
    response: Response,
    current_user=Depends(get_current_user),
    _: None = Depends(verify_csrf),
    repo = Depends(get_chat_respository)
) -> dict:
    del current_user, _
    session_id = request.headers.get("X-Session-Id")

    response.delete_cookie(key=auth_cookie_name(session_id), path="/")
    response.delete_cookie(key=csrf_cookie_name(session_id), path="/")   
    #end session
    repo.end_session(session_id)
    return {"message": "Logged out"}


@app.post("/summary",  tags=["Summary"])
async def record_summary(request: Request, 
                         current_user=Depends(get_current_user),
                         repo = Depends(get_chat_respository)):
    session_id = request.headers.get("X-Session-Id")
    messages = repo.get_messages(session_id)
    if not messages:
        logger.error("Session has no messages to summarise.")
        return {"status": "no messages to summarise"}
    else:
        if not session_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing session id")
        transcript = build_transcript(messages)
        safe_transcript = repo.masker.mask(transcript)
        await get_response_from_agent(
        f'summarize the following {session_id}:{safe_transcript}', user_id=current_user["user_id"], session_id=session_id
        )
        return {"status": "summary recorded"}

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_endpoint(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    _: None = Depends(verify_csrf),
    repo = Depends(get_chat_respository)
):
    try:        

        lang = detect_language(request.message or "")
        session_id = request.session_id

        # 0) Ensure session exists in DB
        repo.create_session(
            user_id=current_user["user_id"],
            user_name=current_user["username"],
            session_id=session_id,
        )

        # 1) Mask user's message before DB storage 
        masked_user_message = repo.masker.mask(request.message)
        repo.save_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=masked_user_message,
        )

        # 2) Guardrails input
        is_safe_input, input_reason = await check_guardrails_input(request.message)
        if not is_safe_input:
            response = input_reason if input_reason else (
                    ".أسف ، لا أستطيع تنفيذ طلبك بسبب سياسات الاستخدام"
                    if lang == "ar"
                    else "I'm sorry, I cannot process your request due to policy restrictions."
                )
            repo.save_message(
                session_id=session_id,
                role=MessageRole.MODEL,
                        content=response,
            )

            return ChatResponse(
                response=response,
                status="completed",
            )

        # 3) Create/update ADK session state
        session = await SESSION_SERVICE.get_session(
            app_name=APP_NAME,
            user_id=current_user["user_id"],
            session_id=session_id,
        )

        # IMPORTANT: routing_agent.send_message reads state["user_jwt"]
        current_request_state = {
            "user_id": current_user["user_id"],
            "username": current_user["username"],
            "session_id": session_id
        }

        if not session:
            logger.info(f"Creating new ADK session with id '{session_id}'")
            logger.info(f"Creating new session with state: {current_request_state}")
            await SESSION_SERVICE.create_session(
                app_name=APP_NAME,
                user_id=current_user["user_id"],
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
        start_time = time.time()
        
        response_text = await get_response_from_agent(
            request.message, user_id=current_user["user_id"], session_id=session_id
        )
        
        duration = time.time() - start_time
        logger.info(f"Response time for session {session_id}: {duration:.2f}s")

        if "Agent escalated" in response_text or "please contact our customer service team" in response_text.lower() or "يرجى الاتصال بفريق خدمة العملاء" in response_text:
            logger.info(f"Agent escalated for session {session_id}")

        # If the agent responded in Arabic, prefer that for downstream messages
        lang = detect_language(response_text or request.message or "")

        # 6) Guardrails output
        is_safe_output, filtered, out_reason = await check_guardrails_output(response_text)
        final_response = (
            filtered if (is_safe_output and filtered is not None) else (
                out_reason if out_reason else (
                    "تم حظر الاستجابة بواسطة قواعد السياسة."
                    if lang == "ar"
                    else "Response blocked by policy rules."
                )
            )
        )

        # 6) Mask model reply before DB storage
        masked_reply = repo.masker.mask(final_response)
        repo.save_message(
            session_id=session_id,
            role=MessageRole.MODEL,
            content=masked_reply,
        )

        # Language detection via script analysis
        language = Language.AR if detect_language(final_response) == "ar" else Language.EN
        
        logger.info(f"Language for session {session_id}: {language}")

        return ChatResponse(
            response=final_response or (
                "لم يتم تلقي أي رد"
                if lang == "ar"
                else "No response generated"
            ),
            status="completed"
        )

    except Exception as e:
        logger.exception(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.post("/voice_chat", response_model=VoiceChatResponse, tags=["Chat"])
async def voice_chat_endpoint(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    current_user=Depends(get_current_user),
    repo = Depends(get_chat_respository)
):
    try:
        # 1) Speech-to-Text: Convert audio to text
        async with httpx.AsyncClient(timeout=30.0) as client:
            stt_response = await client.post(
                f"{VOICE_SERVICE_URL}/voice_service/stt",
                files={"audio": (audio.filename, await audio.read(), audio.content_type)}
            )
            stt_response.raise_for_status()
            stt_data = stt_response.json()
            user_message = stt_data.get("text")
            logger.info(f"[VOICE] Transcription received for session {session_id}: '{user_message}'")

        if not user_message:
            # If transcription is empty but succeeded (silence), we can just return early or log it.
            return VoiceChatResponse(
                user_message="",
                response=".عذراً، لم أستطع سماع أي شيء. يرجى المحاولة مرة أخرى" if detect_language("") == "ar" else "I'm sorry, I couldn't hear anything. Please try again.",
                status="completed"
            )

        # 2) Ensure session exists in DB and ADK memory
        repo.create_session(
            user_id=current_user["user_id"],
            user_name=current_user["username"],
            session_id=session_id,
        )

        session = await SESSION_SERVICE.get_session(
            app_name=APP_NAME,
            user_id=current_user["user_id"],
            session_id=session_id,
        )

        current_request_state = {
            "user_id": current_user["user_id"],
            "username": current_user["username"],
            "session_id": session_id
        }

        if not session:
            logger.info(f"Creating new ADK session for Voice with id '{session_id}'")
            await SESSION_SERVICE.create_session(
                app_name=APP_NAME,
                user_id=current_user["user_id"],
                session_id=session_id,
                state=current_request_state or {},
            )
        else:
            try:
                actions = EventActions(state_delta=current_request_state)
                event = Event(
                    invocation_id="voice_bridge_state_update",
                    author="host_agent_voice",
                    actions=actions,
                )
                await SESSION_SERVICE.append_event(session, event)
            except Exception as exc:
                logger.warning(f"[VOICE-DEBUG] Failed to append session state: {exc}")

        # 3) Process with Agent
        
        # Log user message
        repo.save_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=f"[VOICE] {user_message}",
        )

        # Get agent response
        response_text = await get_response_from_agent(
            user_message, user_id=current_user["user_id"], session_id=session_id
        )

        # 4) Text-to-Speech: Convert response to audio
        lang_code = detect_language(response_text)
        async with httpx.AsyncClient(timeout=30.0) as client:
            tts_response = await client.post(
                f"{VOICE_SERVICE_URL}/voice_service/tts",
                json={"text": response_text, "language_code": lang_code}
            )
            tts_response.raise_for_status()
            tts_data = tts_response.json()
            audio_base64 = tts_data.get("audio_base64")

        # Log agent response
        repo.save_message(
            session_id=session_id,
            role=MessageRole.MODEL,
            content=f"[VOICE] {response_text}",
        )

        return VoiceChatResponse(
            user_message=user_message,
            response=response_text,
            audio_base64=audio_base64,
            status="completed"
        )

    except Exception as e:
        logger.exception(f"Error in voice_chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
# =========================
# Startup Hook
# =========================

@app.on_event("startup")
async def startup_event():
    global ROUTING_AGENT_RUNNER

    logger.info("Initializing Routing Agent...")
    await routing_agent_module.init_routing_agent()

    logger.info("Creating ADK session...")
    await SESSION_SERVICE.create_session(
        app_name=APP_NAME,
        user_id=DEFAULT_USER_ID,
        session_id=DEFAULT_SESSION_ID,
    )

    logger.info("Initializing Database...")
    init_db()
    
    logger.info("Initializing Runner...")
    ROUTING_AGENT_RUNNER = Runner(
        agent=routing_agent_module.root_agent,  # initialized by init_routing_agent()
        app_name=APP_NAME,
        session_service=SESSION_SERVICE,
        memory_service=MEMORY_SERVICE,
    )

def main():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
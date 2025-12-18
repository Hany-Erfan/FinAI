from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.host_agent.routes.login import get_current_user_optional, security
from backend.host_agent.routing_agent import get_root_agent_async, AuthRequiredError
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.events import Event, EventActions
from google.genai import types
from backend.host_agent.schemas import ChatMessage, ChatResponse

router = APIRouter()
APP_NAME = "routing_app"
SESSION_SERVICE = InMemorySessionService()
MEMORY_SERVICE = InMemoryMemoryService()



@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    chat_message: ChatMessage,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), # Security is now also optional/handled by get_current_user_optional logic implicitly via Depends structure, but we need credentials object if present. Actually get_current_user_optional handles the extraction.
):
    """Chat endpoint that bridges HTTP requests to A2A host agent."""
    try:
        if current_user:
            user_id = str(current_user.get("user_id", "default_user"))
            jwt_token = credentials.credentials if credentials else None
        else:
            user_id = "guest_user" 
            jwt_token = None

        # Logic: If frontend sends a session_id (e.g. "session_123..."), use it.
        # This allows preserving context even if user_id changes (guest -> logged in).
        if chat_message.session_id:
             session_id = chat_message.session_id
        else:
             session_id = f"session_{user_id}"

        session = await SESSION_SERVICE.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

        # Prepare state for new sessions or for updates to existing sessions.
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
            # Merge the latest JWT/user + media info so tools see current attachments
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

        # Obtain the initialized root agent (lazily initialized during login)
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
            return ChatResponse(response=response_text or "No response generated", status="completed")
        except AuthRequiredError:
            print("DEBUG: AuthRequiredError caught in chat_endpoint. Returning [AUTH_REQUIRED]")
            return ChatResponse(response="[AUTH_REQUIRED]")
            
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_agent_events(event_iterator) -> str:
    """Process events from the agent runner and extract response.
    
    Args:
        event_iterator: Async iterator of events from the agent runner
        
    Returns:
        The final response text from the agent
    """
    response_text = ""
    
    async for event in event_iterator:
        print(f"[HTTP-DEBUG] Event type: {type(event)}")
        print(f"[HTTP-DEBUG] Is final: {event.is_final_response()}")
        print(f"[HTTP-DEBUG] Content: {event.content}")
        
        if event.is_final_response():
            # Try to get the final response text
            if event.content and event.content.parts:
                final_text = "".join(
                    [p.text for p in event.content.parts if p.text]
                ).strip()
                print(f"[HTTP-DEBUG] Final response text: '{final_text}'")
                if final_text:
                    response_text = final_text
                    # Only break if we actually have content
                    break
            # If final response has no content, continue waiting for more events
            print("[HTTP-DEBUG] Final event with no content, continuing...")
        else:
            # Process all parts in the event
            if event.content and event.content.parts:
                for part in event.content.parts:
                    # Check for text parts
                    if part.text and part.text.strip():
                        intermediate_text = part.text.strip()
                        print(f"[HTTP-DEBUG] Intermediate text: '{intermediate_text}'")
                        response_text += intermediate_text + " "
                    # Check for function_response parts and extract the result
                    elif hasattr(part, "function_response") and part.function_response:
                        func_response = part.function_response
                        if (
                            hasattr(func_response, "response")
                            and func_response.response
                        ):
                            result = func_response.response.get("result", "")
                            if result and isinstance(result, str):
                                print(
                                    f"[HTTP-DEBUG] Function response result: '{result}'"
                                )
                                # Store this as a fallback response
                                if not response_text or response_text.strip() == "":
                                    response_text = result
    
    return response_text
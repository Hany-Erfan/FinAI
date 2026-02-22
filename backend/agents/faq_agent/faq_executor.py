import logging

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    FilePart,
    FileWithBytes,
    FileWithUri,
    Part,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils.errors import ServerError
from google.genai import types
from backend.agents.faq_agent.faq_agent import ProductAgent


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class FAQExecutor(AgentExecutor):
    """An AgentExecutor that runs an ADK-based Agent for FAQ."""

    def __init__(self, card: AgentCard):
        self._card = card
        # Track active sessions for potential cancellation
        self._active_sessions: set[str] = set()

    def _prepare_session_state(self, jwt_token: str, user_id: str) -> dict:
        """
        Constructs the session state dictionary for the agent run.

        This includes authentication details (JWT, user ID) and
        extracts the base64-encoded image data and MIME type from the
        incoming message parts, if present.

        :param jwt_token: The JWT token for session state.
        :type jwt_token: str
        :param user_id: The user ID for the session.
        :type user_id: str
        :return: A dictionary containing the session state.
        :rtype: dict
        """
        session_state: dict = {}
        try:
            if jwt_token:
                session_state["jwt_token"] = jwt_token
            if user_id:
                session_state["user_id"] = user_id

        except Exception:
            # Do not fail request on image extraction issues
            pass
        
        return session_state

    async def _process_request(
        self,
        new_message: types.Content,
        session_id: str,
        task_updater: TaskUpdater,
        jwt_token: str = None,
        user_id: str = None,
    ) -> None:
        """Process request using cached FAQAgent instance."""
        # Get cached FAQ agent for this user
        faq_agent = ProductAgent.get_agent(user_id=user_id)
        
        session_state = self._prepare_session_state(
            jwt_token, user_id
        )
        
        # Create or get session
        session_obj = await faq_agent._get_or_create_session(
            user_id=user_id,
            session_id=session_id,
            session_state=session_state
        )
        session_id = session_obj.id

        # Track this session as active
        self._active_sessions.add(session_id)

        try:
            async for event in faq_agent.runner.run_async(
                session_id=session_id,
                user_id=user_id,
                new_message=new_message,
            ):
                if event.is_final_response():
                    parts = [
                        convert_genai_part_to_a2a(part)
                        for part in event.content.parts
                        if (part.text or part.file_data or part.inline_data)
                    ]
                    logger.debug('Yielding final response: %s', parts)
                    await task_updater.add_artifact(parts)
                    await task_updater.update_status(
                        TaskState.completed, final=True
                    )
                    break
                if not event.get_function_calls():
                    logger.debug('Yielding update response')
                    await task_updater.update_status(
                        TaskState.working,
                        message=task_updater.new_agent_message(
                            [
                                convert_genai_part_to_a2a(part)
                                for part in event.content.parts
                                if (
                                    part.text
                                    or part.file_data
                                    or part.inline_data
                                )
                            ],
                        ),
                    )
                else:
                    logger.debug('Skipping event')
        finally:
            # Remove from active sessions when done
            self._active_sessions.discard(session_id)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ):
        # Extract JWT token and user credentials from message metadata
        jwt_token = None
        user_id = 'self'
        
        if hasattr(context.message, 'metadata') and context.message.metadata:
            jwt_token = context.message.metadata.get("jwt_token")
            user_id = context.message.metadata.get("user_id", 'self')
            logger.debug(f'[FAQ] Extracted metadata - user_id: {user_id}')
        else:
            logger.debug('[FAQ] No metadata found in message')
        
        # Run the agent until either complete or the task is suspended.
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        # Immediately notify that the task is submitted.
        if not context.current_task:
            await updater.update_status(TaskState.submitted)
        await updater.update_status(TaskState.working)
        await self._process_request(
            types.UserContent(
                parts=[
                    convert_a2a_part_to_genai(part)
                    for part in context.message.parts
                ],
            ),
            context.context_id,
            updater,
            jwt_token=jwt_token,
            user_id=user_id,
        )
        logger.debug('[FAQ] execute exiting')

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """Cancel the execution for the given context.

        Currently logs the cancellation attempt as the underlying ADK runner
        doesn't support direct cancellation of ongoing tasks.
        """
        session_id = context.context_id
        if session_id in self._active_sessions:
            logger.info(
                f'Cancellation requested for active FAQ session: {session_id}'
            )
            # TODO: Implement proper cancellation when ADK supports it
            self._active_sessions.discard(session_id)
        else:
            logger.debug(
                f'Cancellation requested for inactive FAQ session: {session_id}'
            )

        raise ServerError(error=UnsupportedOperationError())


def convert_a2a_part_to_genai(part: Part) -> types.Part:
    """Convert a single A2A Part type into a Google Gen AI Part type.

    Args:
        part: The A2A Part to convert

    Returns:
        The equivalent Google Gen AI Part

    Raises:
        ValueError: If the part type is not supported
    """
    part = part.root
    if isinstance(part, TextPart):
        return types.Part(text=part.text)
    if isinstance(part, FilePart):
        if isinstance(part.file, FileWithUri):
            return types.Part(
                file_data=types.FileData(
                    file_uri=part.file.uri, mime_type=part.file.mime_type
                )
            )
        if isinstance(part.file, FileWithBytes):
            return types.Part(
                inline_data=types.Blob(
                    data=part.file.bytes, mime_type=part.file.mime_type
                )
            )
        raise ValueError(f'Unsupported file type: {type(part.file)}')
    raise ValueError(f'Unsupported part type: {type(part)}')


def convert_genai_part_to_a2a(part: types.Part) -> Part:
    """Convert a single Google Gen AI Part type into an A2A Part type.

    Args:
        part: The Google Gen AI Part to convert

    Returns:
        The equivalent A2A Part

    Raises:
        ValueError: If the part type is not supported
    """
    if part.text:
        return TextPart(text=part.text)
    if part.file_data:
        return FilePart(
            file=FileWithUri(
                uri=part.file_data.file_uri,
                mime_type=part.file_data.mime_type,
            )
        )
    if part.inline_data:
        return Part(
            root=FilePart(
                file=FileWithBytes(
                    bytes=part.inline_data.data,
                    mime_type=part.inline_data.mime_type,
                )
            )
        )
    raise ValueError(f'Unsupported part type: {part}')
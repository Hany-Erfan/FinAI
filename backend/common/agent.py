import os
from typing import Optional
from google.adk.agents import Agent as GoogleAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.events import Event, EventActions
from abc import ABC, abstractmethod
from google.adk.artifacts import InMemoryArtifactService


class Agent(ABC):
    """Generic agent runner that encapsulates turn execution and session handling.

    Instantiate with an application name and a configured GoogleAgent; then call
    methods to manage sessions or access the runner.
    """

    def __init__(
            self,
            *,
            app_name: str,
            google_agent: GoogleAgent,
    ) -> None:
        """Initialize a concrete agent instance.

        :param app_name: The name of the application (used for session storage keys)
        :type app_name: str
        :param google_agent: The configured ADK Agent instance
        :type google_agent: google.adk.agents.Agent
        :return: None
        :rtype: None
        """
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY environment variable not set. Please provide a valid API key.")

        self.app_name = app_name
        self.google_agent = google_agent
        self._session_service = InMemorySessionService()
        self._memory_service = InMemoryMemoryService()
        self._artifact_service = InMemoryArtifactService()

        self.runner = Runner(
            agent=self.google_agent,
            app_name=self.app_name,
            session_service=self._session_service,
            memory_service=self._memory_service,
            artifact_service=self._artifact_service,
        )

    async def _get_or_create_session(
            self, user_id: str, session_id: str, session_state: Optional[dict] = None
    ):
        """Ensure a session exists and optionally merge state.

        :param user_id: Unique user identifier
        :type user_id: str
        :param session_id: Session identifier within this app
        :type session_id: str
        :param session_state: Optional state to merge into the session
        :type session_state: Optional[dict]
        :return: The created or fetched session object
        :rtype: google.adk.sessions.Session
        """
        session = await self._session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if not session:
            print(f"Creating new session with state: {session_state}")
            session = await self._session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
                state=session_state or {},
            )
        else:
            if session_state is not None:
                # Update state via append_event to ensure proper tracking and persistence
                actions = EventActions(state_delta=session_state)
                event = Event(
                    invocation_id="session_state_update",
                    author="system",
                    actions=actions,
                )
                await self._session_service.append_event(session, event)
                print(
                    f"Appended state_delta event. Keys: {list(session_state.keys())}. "
                )
        return session

    @classmethod
    @abstractmethod
    def get_agent(cls, user_id: str) -> "Agent":
        """Return a cached or new agent instance.

        :param user_id: Cache key for the user.
        :type user_id: str
        :return: Agent instance bound to the user context.
        :rtype: Agent
        """
        pass


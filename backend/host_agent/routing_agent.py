# pylint: disable=logging-fstring-interpolation
import json
import os
import uuid

from typing import Any

import httpx

from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    Part,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
    TaskState,
)
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.tool_context import ToolContext
from backend.host_agent.remote_agent_connection import (
    RemoteAgentConnections,
    TaskUpdateCallback,
)


REQUEST_TIMEOUT = 120.0



class AuthRequiredError(Exception):
    """Raised when authentication is required for a guest user."""
    pass


def convert_part(part: Part, tool_context: ToolContext):
    """Convert a part to text. Only text parts are supported."""
    if part.type == 'text':
        return part.text

    return f'Unknown type: {part.type}'


def convert_parts(parts: list[Part], tool_context: ToolContext):
    """Convert parts to text."""
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
    payload: dict[str, Any] = {
        'message': {
            'role': 'user',
            'parts': [{'type': 'text', 'text': text}],
            'messageId': uuid.uuid4().hex,
        },
    }

    if task_id:
        payload['message']['taskId'] = task_id

    if context_id:
        payload['message']['contextId'] = context_id
    return payload

class RoutingAgent:
    """The Routing agent.

    This is the agent responsible for choosing which remote seller agents to send
    tasks to and coordinate their work.
    """

    def __init__(
        self,
        task_callback: TaskUpdateCallback | None = None,
    ):
        """Initializes the RoutingAgent.

        :param task_callback: Callback function for task updates.
        :type task_callback: TaskUpdateCallback | None
        """
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ''

    async def _async_init_components(
        self, remote_agent_addresses: list[str]
    ) -> None:
        """Asynchronously initializes the components of the RoutingAgent.

        :param remote_agent_addresses: A list of remote agent addresses.
        :type remote_agent_addresses: list[str]
        """
        # Use a single httpx.AsyncClient for all card resolutions for efficiency
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(
                    client, address
                )  # Constructor is sync
                try:
                    card = (
                        await card_resolver.get_agent_card()
                    )  # get_agent_card is async

                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    print(
                        f'ERROR: Failed to get agent card from {address}: {e}'
                    )
                except Exception as e:  # Catch other potential errors
                    print(
                        f'ERROR: Failed to initialize connection for {address}: {e}'
                    )

        # Populate self.agents using the logic from original __init__ (via list_remote_agents)
        agent_info = []
        for agent_detail_dict in self.list_remote_agents():
            agent_info.append(json.dumps(agent_detail_dict))
        self.agents = '\n'.join(agent_info)

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: list[str],
        task_callback: TaskUpdateCallback | None = None,
    ) -> 'RoutingAgent':
        """Creates and asynchronously initializes an instance of the RoutingAgent.

        :param remote_agent_addresses: A list of remote agent addresses.
        :type remote_agent_addresses: list[str]
        :param task_callback: Callback function for task updates.
        :type task_callback: TaskUpdateCallback | None
        :return: An instance of the RoutingAgent.
        :rtype: RoutingAgent
        """
        instance = cls(task_callback)
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def create_agent(self) -> Agent:
        """Creates an instance of the RoutingAgent.

        :return: An instance of the RoutingAgent.
        :rtype: Agent
        """
        return Agent(
            model='gemini-3-flash-preview',
            name='Routing_agent',
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                'This Routing agent orchestrates the decomposition of the user asking for Bank products'
            ),
            tools=[
                self.send_message,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        """Generates the root instruction for the RoutingAgent.

        :param context: The readonly context.
        :type context: ReadonlyContext
        :return: The root instruction.
        :rtype: str
        """
        current_agent = self.check_active_agent(context)
        return f"""
        **Role:** You are an expert Routing/Orchestrator Delegator. Your primary function is to accurately delegate user inquiries regarding retail banking services and product information to the appropriate specialized remote agent (Retail Agent or FAQ Agent).

        **Core Directives:**

        * **FAQ Agent Routing:**
        - **When to Engage:** Route to FAQ Agent for general inquiries about banking products, frequently asked questions, and product specifications that do NOT require user account access.
        - **Key Capabilities:** 
          - Expert in bilingual (English/Arabic) product details (e.g., Certificates, Loans).
          - Answers questions about interest rates, payout frequencies, and penalties.
          - Does not require a User ID (suitable for guests).
        
        * **Retail Agent Routing:**
        - **When to Engage:** Route to Retail Agent ONLY for user-specific banking queries including:
          - Account balance inquiries
          - Account information and details
          - Transaction history and statements
        - **Key Capabilities:** 
          - Retrieves real-time account balances and available funds
          - Provides detailed account information
          - Fetches transaction history with customizable limits
        
        * **Talk to the user directly:** Do not delegate user queries like hello or any questions that you can directly answer yourself to the remote agents.
        * **Task Delegation:** Utilize the `send_message` function to assign actionable tasks to remote agents.
        * **Response Format:** If the response from the remote agent is in markdown format, show it to the user as it is, if not, format it in markdown.
        * **Contextual Awareness for Remote Agents:** If a remote agent repeatedly requests user confirmation, assume it lacks access to the full conversation history. In such cases, enrich the task description with all necessary contextual information relevant to that specific agent.
        * **Autonomous Agent Engagement:** Never seek user permission before engaging with remote agents. If multiple agents are required to fulfill a request, connect with them directly without requesting user preference or confirmation.
        * **Transparent Communication:** Always present the complete and detailed response from the remote agent to the user.
        * **User Confirmation Relay:** If a remote agent asks for confirmation, and the user has not already provided it, relay this confirmation request to the user.
        * **Focused Information Sharing:** Provide remote agents with only relevant contextual information. Avoid extraneous details.
        * **No Redundant Confirmations:** Do not ask remote agents for confirmation of information or actions.
        * **Tool Reliance:** Strictly rely on available tools to address user requests. Do not generate responses based on assumptions. If information is insufficient, request clarification from the user.
        * **Prioritize Recent Interaction:** Focus primarily on the most recent parts of the conversation when processing requests.
        * **Active Agent Prioritization:** If an active agent is already engaged, route subsequent related requests to that agent using the appropriate task update tool.
        * **Be concise and to the point**: Don't be verbose and don't be too friendly. Be concise and to the point.

        ## **Response Style**
        - **ACT ANONYMOUSLY**: Never show the user your name or the name of the agent you are talking to.
        - **BE CONCISE**: Use minimum words necessary. Avoid explanatory fluff.
        - **Structure with Markdown:** Headers (##), bold for critical info, tables for comparisons, bullets for lists
        - **Use Tables**: Use tables to show results of the tools and the agents as much as possible to be more readable and easier to understand.
        - **Format:**
          - Usernames, balances, and other critical information in **bold**
          - Warnings in **bold** or > blockquotes
          - Multi-step processes as numbered lists

        **Agent Roster:**
        * Available Agents: `{self.agents}`
        * Currently Active Agent: `{current_agent['active_agent']}`
        """

    def check_active_agent(self, context: ReadonlyContext):
        """Checks the active agent.

        :param context: The readonly context.
        :type context: ReadonlyContext
        :return: A dictionary containing the active agent.
        :rtype: dict
        """
        state = context.state
        if (
            'session_id' in state
            and 'session_active' in state
            and state['session_active']
            and 'active_agent' in state
        ):
            return {'active_agent': f'{state["active_agent"]}'}
        return {'active_agent': 'None'}

    def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        """Callback function before the model is called.

        :param callback_context: The callback context.
        :type callback_context: CallbackContext
        :param llm_request: The LLM request.
        :type llm_request: Any
        """
        state = callback_context.state
        if 'session_active' not in state or not state['session_active']:
            if 'session_id' not in state:
                state['session_id'] = str(uuid.uuid4())
            state['session_active'] = True

    def list_remote_agents(self):
        """Lists the available remote agents.

        :return: A list of remote agents.
        :rtype: list
        """
        if not self.cards:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            print(f'Found agent card: {card.model_dump(exclude_none=True)}')
            print('=' * 100)
            remote_agent_info.append(
                {'name': card.name, 'description': card.description}
            )
        return remote_agent_info

    def _handle_agent_switching(self, state: dict, agent_name: str) -> None:
        """Handles agent switching.

        :param state: The state.
        :type state: dict
        :param agent_name: The name of the agent.
        :type agent_name: str
        """
        previous_agent = state.get("active_agent")
        if previous_agent and previous_agent != agent_name:
            state["context_id"] = None
            state["task_id"] = None
            print(
                f"DEBUG: Switching from {previous_agent} to {agent_name} - starting fresh context"
            )

    def _get_task_id(self, state: dict) -> str | None:
        """Gets the task ID from the state.

        :param state: The state.
        :type state: dict
        :return: The task ID.
        :rtype: str | None
        """
        if "task_id" in state and state["task_id"] is not None:
            return state["task_id"]
        return None

    def _get_or_create_context_id(self, state: dict) -> str:
        """Gets or creates a context ID.

        :param state: The state.
        :type state: dict
        :return: The context ID.
        :rtype: str
        """
        if "context_id" in state and state["context_id"] is not None:
            return state["context_id"]
        context_id = str(uuid.uuid4())
        print(f"DEBUG: Generated new context_id: {context_id}")
        return context_id

    def _extract_message_metadata(self, state: dict) -> tuple[str, dict]:
        """Extracts message metadata from the state.

        :param state: The state.
        :type state: dict
        :return: A tuple containing the message ID and metadata.
        :rtype: tuple[str, dict]
        """
        message_id = ""
        metadata = {}
        if "input_message_metadata" in state:
            metadata.update(**state["input_message_metadata"])
            if "message_id" in state["input_message_metadata"]:
                message_id = state["input_message_metadata"]["message_id"]
        if not message_id:
            message_id = str(uuid.uuid4())
        return message_id, metadata

    def _add_jwt_to_metadata(self, state: dict, metadata: dict, agent_name: str) -> None:
        """Adds a JWT token to the metadata.

        :param state: The state.
        :type state: dict
        :param metadata: The metadata.
        :type metadata: dict
        :param agent_name: The name of the agent.
        :type agent_name: str
        """
        jwt_token = state.get("jwt_token")
        user_id = state.get("user_id")
        username = state.get("username")
        print(f"[ORCH-DEBUG] state type: {type(state)}")
        print(
            f"[ORCH-DEBUG] jwt_token: {jwt_token is not None if jwt_token else 'None'}"
        )
        print(f"[ORCH-DEBUG] user_id: {user_id}")
        print(f"[ORCH-DEBUG] username: {username}")
        if jwt_token:
            metadata["jwt_token"] = jwt_token
            metadata["user_id"] = user_id
            metadata["username"] = username
            print(f"[ORCH-DEBUG] Passing JWT token to {agent_name} agent")
            print(f"[ORCH-DEBUG] metadata: {metadata}")
        else:
            print(f"[ORCH-DEBUG] No JWT token found in state for {agent_name} agent")

    @staticmethod
    def _create_send_message_payload(
        text: str,
        message_id: str,
        task_id: str | None = None,
        context_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        extra_parts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Creates the payload for sending a message.

        :param text: The text of the message.
        :type text: str
        :param message_id: The ID of the message.
        :type message_id: str
        :param task_id: The ID of the task.
        :type task_id: str | None
        :param context_id: The ID of the context.
        :type context_id: str | None
        :param metadata: The metadata.
        :type metadata: dict[str, Any] | None
        :param extra_parts: Extra parts to include in the message.
        :type extra_parts: list[dict[str, Any]] | None
        :return: The payload.
        :rtype: dict[str, Any]
        """
        parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
        if extra_parts:
            parts.extend(extra_parts)
        payload: dict[str, Any] = {
            "message": {
                "role": "user",
                "parts": parts,
                "messageId": message_id,
            },
        }
        if task_id is not None:
            payload["message"]["taskId"] = task_id
        if context_id:
            payload["message"]["contextId"] = context_id
        if metadata:
            payload["message"]["metadata"] = metadata
        return payload

    @staticmethod
    def _handle_task_result(task_result: Task, state: dict, agent_name: str) -> str:
        """Handles the result of a task.

        :param task_result: The result of the task.
        :type task_result: Task
        :param state: The state.
        :type state: dict
        :param agent_name: The name of the agent.
        :type agent_name: str
        :return: The result of the task.
        :rtype: str
        """
        if task_result.status.state == TaskState.input_required:
            state["task_id"] = task_result.id
            state["context_id"] = task_result.context_id
            agent_question = "Input required"
            try:
                if task_result.status.message and task_result.status.message.parts:
                    first_part = task_result.status.message.parts[0]
                    # Support both .root.text and .text shapes
                    text_val = getattr(getattr(first_part, "root", None), "text", None) or getattr(first_part, "text", None)
                    if text_val:
                        agent_question = text_val
            except Exception:
                pass
            print(f"DEBUG: Agent requires input: {agent_question}")
            return f"The {agent_name} agent needs more information: {agent_question}"
        elif task_result.status.state == TaskState.completed:
            agent_response = ""
            try:
                if task_result.artifacts and len(task_result.artifacts) > 0:
                    art = task_result.artifacts[0]
                    if getattr(art, "parts", None) and len(art.parts) > 0:
                        first_part = art.parts[0]
                        text_val = getattr(getattr(first_part, "root", None), "text", None) or getattr(first_part, "text", None)
                        if text_val:
                            agent_response = text_val
            except Exception:
                pass
            state["task_id"] = None
            state["context_id"] = task_result.context_id
            if agent_response:
                return agent_response
            return f"Task completed by {agent_name} (no textual response)"
        else:
            state["task_id"] = task_result.id
            state["context_id"] = task_result.context_id
            return f"Task sent to {agent_name}. Status: {task_result.status.state}"


    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """Sends a task to a remote seller agent.

        This will send a message to the remote agent named agent_name.

        :param agent_name: The name of the agent to send the task to.
        :type agent_name: str
        :param task: The comprehensive conversation context summary
            and goal to be achieved regarding user inquiry and purchase request.
        :type task: str
        :param tool_context: The tool context this method runs in.
        :type tool_context: ToolContext
        :yield: A dictionary of JSON data.
        :rtype: dict
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'Agent {agent_name} not found')
        state = tool_context.state
        
        # --- Auth Check ---
        user_id = state.get("user_id", "")
        # Check if the user is a guest (starts with "guest_") and trying to access Retail Agent
        if agent_name == "Retail Agent" and (not user_id or user_id.startswith("guest_")):
            print(f"DEBUG: Auth required for {agent_name} with user_id {user_id}")
            raise AuthRequiredError()
        # ------------------

        self._handle_agent_switching(state, agent_name)
        state["active_agent"] = agent_name
        client = self.remote_agent_connections[agent_name]

        if not client:
            raise ValueError(f'Client not available for {agent_name}')
        task_id = self._get_task_id(state)
        context_id = self._get_or_create_context_id(state)
        message_id, metadata = self._extract_message_metadata(state)
        self._add_jwt_to_metadata(state, metadata, agent_name)

        payload = self._create_send_message_payload(
            text=task,
            message_id=message_id,
            task_id=task_id,
            context_id=context_id,
            metadata=metadata if metadata else None,
        )

        message_request = SendMessageRequest(
            id=message_id, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = await client.send_message(
            message_request=message_request
        )
        print(
            'send_response',
            send_response.model_dump_json(exclude_none=True, indent=2),
        )

        if not isinstance(send_response.root, SendMessageSuccessResponse):
            print('received non-success response. Aborting get task ')
            return None

        if not isinstance(send_response.root.result, Task):
            print('received non-task response. Aborting get task ')
            return None

        task_result = send_response.root.result
        print(f"DEBUG: Task result: {task_result}")
        return self._handle_task_result(task_result, state, agent_name)


def get_initialized_routing_agent() -> Agent:
    """Gets the initialized routing agent.

    :raises RuntimeError: If the agent is not initialized.
    :return: The initialized routing agent.
    :rtype: Agent
    """
    raise RuntimeError(
        "get_initialized_routing_agent is deprecated. Use await init_root_agent() or await get_root_agent_async()."
    )


# ----------------------------
# Lazy async initialization API
# ----------------------------
_CACHED_ROOT_AGENT: Agent | None = None

async def init_root_agent() -> Agent:
    """Initializes the root agent.

    :return: The root agent.
    :rtype: Agent
    """
    global _CACHED_ROOT_AGENT
    if _CACHED_ROOT_AGENT is not None:
        return _CACHED_ROOT_AGENT
    
    print("[SERVER] Initializing root agent...")
    print("[SERVER] Retail Agent URL: ", os.getenv("RETAIL_AGENT_URL", "http://localhost:8002"))

    routing_agent_instance = await RoutingAgent.create(
        remote_agent_addresses=[
            os.getenv("RETAIL_AGENT_URL", "http://localhost:8002"),
            os.getenv("FAQ_AGENT_URL", "http://localhost:8001"),
        ]
    )
    _CACHED_ROOT_AGENT = routing_agent_instance.create_agent()
    return _CACHED_ROOT_AGENT


async def get_root_agent_async() -> Agent:
    """Gets the root agent asynchronously.

    :return: The root agent.
    :rtype: Agent
    """
    return await init_root_agent()


def get_root_agent_cached() -> Agent:
    """Gets the cached root agent.

    :raises RuntimeError: If the root agent is not initialized.
    :return: The cached root agent.
    :rtype: Agent
    """
    if _CACHED_ROOT_AGENT is None:
        raise RuntimeError("Root agent is not initialized yet. Initialize it in an async context first.")
    return _CACHED_ROOT_AGENT


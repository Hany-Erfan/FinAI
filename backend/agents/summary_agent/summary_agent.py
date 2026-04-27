import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
)
from backend.common.agent import Agent
from backend.common.cache_dict import SummaryAgentCache


def create_summary_agent(user_id: str, session_id: str) -> LlmAgent:
    """Constructs the ADK agent using MCP."""
    return LlmAgent(
        model=os.getenv("SUMMARY_AGENT_MODEL_ID", "gemini-3-flash-preview"),
        name='summary_agent',
        description='Analyses the whole transcript and records structured summaries.',
        instruction=f"""
                You are an expert summarizing agent for this {user_id}.
                You will receive a masked conversation transcript (PII has been replaced
                with placeholders like <EMAIL_1>) that starts with summarize the following {session_id}:
                Extract the {session_id} as input for your tool but for summarization
                Consider only the part after the : as a transcript
                Your job is to analyse this output for the current {session_id} once it's ready, 
                use this safe_transcript as the only context for summarization
                and call the `record_summary` EXACTLY ONCE to generate a single output for summarizing the texts
                passed through the transcript input parameter with the following fields at the end:
                - summary_text      : a concise 2-4 sentence prose summary
                - key_topics        : List of topics should be within the following categories ["general","onboarding", 
                "login", "help&support", deposits]). If none of them matches set the key_topics to be as an out of scope category.
                - sentiment         : one of  positive | neutral | negative
                - resolution_status : one of  resolved | unresolved | escalated | unknown
                Afterwards, the output should be saved in the database using the save_summaries.
                Do not output any other text. Call the tool and stop.
                """,
        tools=[
            MCPToolset(
                connection_params=StdioServerParameters(
                    command='python',
                    args=['backend/agents/summary_agent/summary_mcp.py'],
                    env=dict(os.environ),
                ),
            )
        ],
    )


class SummaryAgent(Agent):
    """Summary banking agent with session and caching support."""

    def __init__(self, user_id: str, session_id: str):
        """Initialize the summary agent."""
        # Create the Google ADK agent
        google_agent = create_summary_agent(user_id, session_id)
        
        # Initialize base class
        super().__init__(
            app_name='summary_agent',
            google_agent=google_agent,
        )

    @classmethod
    def get_agent(cls, user_id: str, session_id: str) -> "SummaryAgent":
        """Return a cached or new summary agent instance.

        :param user_id: Cache key for the user
        :type user_id: str
        :return: SummaryAgent instance
        :rtype: SummaryAgent
        """
        if user_id not in SummaryAgentCache:
            print(f"[SUMMARY] Creating new agent instance for user {user_id}")
            SummaryAgentCache[user_id] = cls(user_id, session_id)
        else:
            print(f"[SUMMARY] Using cached agent instance for user {user_id}")
        
        return SummaryAgentCache[user_id]
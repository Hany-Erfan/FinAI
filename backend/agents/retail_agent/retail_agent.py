import os
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
)
from backend.common.agent import Agent
from backend.common.cache_dict import RetailAgentCache


def create_retail_agent(user_id: str) -> LlmAgent:
    """Constructs the ADK agent."""
    return LlmAgent(
        model=os.getenv("RETAIL_AGENT_MODEL_ID", "gemini-3-flash-preview"),
        name='retail_agent',
        description='A retail banking assistant that helps customers with account information, balances, transactions, and product eligibility',
        instruction=f"""You are a specialized retail banking assistant for User ID: {user_id}. Your primary function is to help customers with their banking needs by utilizing the provided tools to retrieve and relay banking information in response to user queries.

        **Your Context:**
        - **Current User ID:** {user_id}
        - You MUST use this User ID when calling tools that require it (e.g., get_balance, get_transactions).

        **Your Capabilities:**
        - Check account balances and available funds
        - Retrieve account information and details
        - View transaction history

        **Important Guidelines:**
        1. You must rely exclusively on the provided tools for data and refrain from inventing information
        2. Always use the tools to fetch real-time banking data
        3. Present all information clearly and professionally
        4. Ensure that all responses include the detailed output from the tools used and are formatted in Markdown
        5. Protect customer privacy and handle all banking information with care
        6. If a tool returns an error, explain it clearly to the customer and suggest alternatives

        **Response Format:**
        - Use tables for structured data (balances, accounts)
        - Use bullet points for transaction lists
        - Use clear headings and sections
        - Include relevant details but keep responses concise and user-friendly""",
        tools=[
            MCPToolset(
                connection_params=StdioServerParameters(
                    command='python',
                    args=['backend/agents/retail_agent/retail_mcp.py'],
                    env=dict(os.environ),
                ),
            )
        ],
    )


class RetailAgent(Agent):
    """Retail banking agent with session and caching support."""

    def __init__(self, user_id: str):
        """Initialize the retail agent."""
        # Create the Google ADK agent
        google_agent = create_retail_agent(user_id)
        
        # Initialize base class
        super().__init__(
            app_name='retail_agent',
            google_agent=google_agent,
        )

    @classmethod
    def get_agent(cls, user_id: str) -> "RetailAgent":
        """Return a cached or new retail agent instance.

        :param user_id: Cache key for the user
        :type user_id: str
        :return: RetailAgent instance
        :rtype: RetailAgent
        """
        if user_id not in RetailAgentCache:
            print(f"[RETAIL] Creating new agent instance for user {user_id}")
            RetailAgentCache[user_id] = cls(user_id)
        else:
            print(f"[RETAIL] Using cached agent instance for user {user_id}")
        
        return RetailAgentCache[user_id]
import os
import logging
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
)
from backend.common.agent import Agent
from backend.common.cache_dict import ProductAgentCache

logger = logging.getLogger(__name__)


def create_product_agent(user_id: str) -> LlmAgent:
    """Constructs the ADK agent."""
    return LlmAgent(
        model='gemini-3-flash-preview',
        name='product_agent',
        description='A bilingual product assistant that answers questions about banking products using RAG.',
        instruction="""You are a specialized bilingual product assistant. Your primary function is to answer user queries regarding banking products by strictly using the provided RAG tool to retrieve information.

        **Core Responsibilities:**
        1.  **Analyze the Query:** Understand the user's question and identify the specific product details they are looking for.
        2.  **Retrieve Information:** Use the RAG tool to find the relevant product information.
        3.  **Strict Answering:** Answer the user's query EXACTLY based on the retrieved data. Do **NOT** provide any additional information about the product that the user did not ask for.
        4.  **Language Adaptation:** You must communicate in the SAME language as the user's query (English or Arabic). If the user asks in Arabic, answer in Arabic. If in English, answer in English.

        **Constraints:**
        - You do **NOT** require a User ID.
        - Do not ask for personal banking details.
        - Rely **only** on the tool output. Do not hallucinate or use outside knowledge.
        
        **Response Style:**
        - Concise and direct.
        - Use Markdown for formatting.
        """,
        tools=[
            MCPToolset(
                connection_params=StdioServerParameters(
                    command='python',
                    args=['backend/agents/faq_agent/faq_mcp.py'],
                    env=dict(os.environ),
                ),
            )
        ],
    )


class ProductAgent(Agent):
    """Product banking agent with session and caching support."""

    def __init__(self, user_id: str):
        """Initialize the retail agent."""
        # Create the Google ADK agent
        google_agent = create_product_agent(user_id)
        
        # Initialize base class
        super().__init__(
            app_name='product_agent',
            google_agent=google_agent,
        )

    @classmethod
    def get_agent(cls, user_id: str) -> "ProductAgent":
        """Return a cached or new Product agent instance.

        :param user_id: Cache key for the user
        :type user_id: str
        :return: ProductAgent instance
        :rtype: ProductAgent
        """
        if user_id not in ProductAgentCache:
            logger.info(f"Creating new agent instance for user {user_id}")
            ProductAgentCache[user_id] = cls(user_id)
        else:
            logger.info(f"Using cached agent instance for user {user_id}")
        
        return ProductAgentCache[user_id]
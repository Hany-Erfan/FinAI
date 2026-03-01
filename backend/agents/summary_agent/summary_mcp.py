
import asyncio
import uuid
from fastapi import Depends
from mcp.server.fastmcp import FastMCP

from backend.agents.summary_agent.summary_agent import SummaryAgent
from backend.common.masking_pii import DataMasker
from backend.host_agent.main import get_session_repository

# Initialize FastMCP server
mcp = FastMCP('summary')

@mcp.tool()
def record_summary(
    summary_text: str,
    key_topics: list[str],
    sentiment: str,
    resolution_status: str,
    ) -> str:
    """
    Record the structured summary of a customer service conversation.

    Args:
    summary_text: A concise 2-4 sentence prose summary of what happened.
    key_topics: List of short topic strings discussed (e.g. onboarding, deposits).
    sentiment: Overall customer sentiment: positive, neutral, or negative.
    resolution_status: Outcome: resolved, unresolved, escalated, or unknown.

    Returns:
        Confirmation string (not used further).
    """
    captured: dict = {}

    captured["summary_text"] = summary_text
    captured["key_topics"] = key_topics
    captured["sentiment"] = sentiment
    captured["resolution_status"] = resolution_status

    if not captured:
        raise RuntimeError(
            "ADK SummaryAgent: `record_summary` tool was never called by the model. "
            "Check the agent instruction or model version."
        )
        
    return "Summary recorded."

if __name__ == '__main__':
    mcp.run(transport='stdio')
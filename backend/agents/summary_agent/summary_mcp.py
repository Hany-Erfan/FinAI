import json
from typing import Any
import httpx
from backend.services.repository_service.routes.get_summary_information import SummaryPayload
from mcp.server.fastmcp import FastMCP
import os


# Initialize FastMCP server
mcp = FastMCP('summary')

# --- Configuration & Constants ---
REPO_URL = os.getenv('REPO_URL', 'http://repository-service:8007')

REQUEST_TIMEOUT = 20.0

# --- Shared HTTP Client ---
http_client = httpx.Client(
    base_url=REPO_URL,
    timeout=REQUEST_TIMEOUT,
    follow_redirects=True,
)


def save_summaries(session_id: str, transcript: SummaryPayload) -> str:
    """
    Saves the generated summary for the corresponding session in the database.
    :return: Saved summary or an error.
    :rtype: str
    """
    endpoint = f'/sessions/{session_id}/save_summaries'
    data = save_summary_response(endpoint, transcript)

    if data is None:
        return f'❌ Failed to save the summary. Please check the Session ID and try again.'

    return data 

def save_summary_response(endpoint: str, transcript: SummaryPayload) -> dict[str, Any] | list[Any] | None:
    """Make a request to the repository API using the shared client with error handling.

    :param endpoint: The endpoint to request.
    :param params: Optional query parameters for the request.

    :return: The response from the the repository API, or None if an error occurs.
    """
    try:
        response = http_client.post(endpoint, json= transcript)
        response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
        return response.json()
    except httpx.HTTPStatusError:
        # Specific HTTP errors (like 404 Not Found, 500 Server Error)
        return None
    except httpx.TimeoutException:
        # Request timed out
        return None
    except httpx.RequestError:
        # Other request errors (connection, DNS, etc.)
        return None
    except json.JSONDecodeError:
        # Response was not valid JSON
        return None
    except Exception:
        # Any other unexpected errors
        return None 
    
# --- MCP Tools ---

@mcp.tool()
def record_summary(
    transcript: str,
    session_id: str,
    summary_text: str,
    key_topics: list[str],
    sentiment: str,
    resolution_status: str,
    ) -> dict:
    """ Record the structured summary of a conversation.

    Args:
    summary_text: A concise 2-4 sentence prose summary of what happened.
    key_topics: topics should be within the following categories ["general","onboarding", "login", "help&support",
                    deposits]). If none of them matches set the key_topics to be as an out of scope category.
    sentiment: Overall customer sentiment: positive, neutral, or negative.
    resolution_status: Outcome: resolved, unresolved, escalated, or unknown.

    Returns:
        Captured string which is used afterwards in save_summaries method. """
    captured: dict = {}
    captured["summary_text"] = summary_text
    captured["key_topics"] = key_topics
    captured["model_used"] = "gemini-3-flash-preview"
    captured["sentiment"] = sentiment
    captured["resolution_status"] = resolution_status
    captured["raw_response"] = transcript
    if not captured:
        raise RuntimeError(
            "ADK SummaryAgent: `record_summary` tool was never called by the model. "
            "Check the agent instruction or model version."
        )
    save_summaries(session_id, captured)
    return captured


# --- Server Execution & Shutdown ---
async def shutdown_event():
    """Gracefully close the httpx client."""
    await http_client.aclose()


if __name__ == '__main__':
    mcp.run(transport='stdio')
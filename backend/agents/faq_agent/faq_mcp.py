import json

from typing import Any

import httpx

from mcp.server.fastmcp import FastMCP
import os


# Initialize FastMCP server
mcp = FastMCP('FAQ')

# --- Configuration & Constants ---
VECTOR_DB_URL = os.getenv('VECTOR_DB_SERVICE_URL')
REQUEST_TIMEOUT = 20.0

# --- Shared HTTP Client ---
http_client = httpx.AsyncClient(
    base_url=VECTOR_DB_URL,
    timeout=REQUEST_TIMEOUT,
    follow_redirects=True,
)

async def get_vector_db_response(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any] | None:
    """Make a request to the vector db API using the shared client with error handling.

    :param endpoint: The endpoint to request.
    :param params: Optional query parameters for the request.

    :return: The response from the vector db API, or None if an error occurs.
    """
    try:
        response = await http_client.get(endpoint, params=params)
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

@mcp.tool()
async def retrieve_product_info(user_query:str) -> str:
    """Retrieves product related information based on user query.

    :param user_query: The user query to retrieve product information for.

    :return: The product information based on the user query.
    """
    endpoint = '/vector_db_service/retreive_product'
    data = await get_vector_db_response(endpoint, params={'user_query': user_query})

    if data is None:
        return '❌ Failed to retrieve product information.'

    return data


# --- Server Execution & Shutdown ---
async def shutdown_event():
    """Gracefully close the httpx client."""
    await http_client.aclose()


if __name__ == '__main__':
    mcp.run(transport='stdio')


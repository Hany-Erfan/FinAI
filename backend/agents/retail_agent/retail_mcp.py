import json

from typing import Any

import httpx

from mcp.server.fastmcp import FastMCP
import os


# Initialize FastMCP server
mcp = FastMCP('retail')

# --- Configuration & Constants ---
BANK_URL = os.getenv('BANK_URL')
REQUEST_TIMEOUT = 20.0

# --- Shared HTTP Client ---
http_client = httpx.AsyncClient(
    base_url=BANK_URL,
    timeout=REQUEST_TIMEOUT,
    follow_redirects=True,
)


async def get_bank_response(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any] | None:
    """Make a request to the bank API using the shared client with error handling.

    :param endpoint: The endpoint to request.
    :param params: Optional query parameters for the request.

    :return: The response from the bank API, or None if an error occurs.
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


# --- MCP Tools ---


@mcp.tool()
async def get_balance(user_id: str) -> str:
    """
    Retrieves detailed balance information for all accounts of a user, including current balance, available balance, currency, and account status.

    :param user_id: The unique identifier of the user.
    :type user_id: str
    :return: A formatted markdown table with balance information for all accounts,
             or an error message if the request fails.
    :rtype: str
    """
    endpoint = f'/user_information/get_balance/{user_id}'
    data = await get_bank_response(endpoint)

    if data is None:
        return f'❌ Failed to retrieve balance for user {user_id}. Please check the user ID and try again.'

    return data 


@mcp.tool()
async def get_accounts(user_id: str) -> str:
    """
    Retrieves all accounts associated with a user, including account type, name, currency, and status information.

    :param user_id: The unique identifier of the user.
    :type user_id: str
    :return: A formatted markdown table with account information,
             or an error message if the request fails.
    :rtype: str
    """
    endpoint = f'/user_information/get_account_type/{user_id}'
    data = await get_bank_response(endpoint)

    if data is None:
        return f'❌ Failed to retrieve accounts for user {user_id}. Please check the user ID and try again.'

    return data


@mcp.tool()
async def get_transactions(user_id: str, limit: int = 10) -> str:
    """
    Retrieves the most recent transactions for a user, including transaction details such as
    date, description, amount, type, and category.

    :param user_id: The unique identifier of the user.
    :type user_id: str
    :param limit: Maximum number of transactions to retrieve (default: 10).
    :type limit: int
    :return: A formatted markdown list with transaction details,
             or an error message if the request fails.
    :rtype: str
    """
    endpoint = f'/user_information/get_transactions/{user_id}'
    params = {'limit': limit}
    data = await get_bank_response(endpoint, params=params)

    if data is None:
        return f'❌ Failed to retrieve transactions for user {user_id}. Please check the user ID and try again.'

    return data


# --- Server Execution & Shutdown ---
async def shutdown_event():
    """Gracefully close the httpx client."""
    await http_client.aclose()


if __name__ == '__main__':
    mcp.run(transport='stdio')
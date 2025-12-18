from backend.bank_server.data.users import users_by_id, users_by_username
from backend.bank_server.data.products import retail_products_by_id

from typing import Any


async def authenticate(username: str, password: str) -> dict[str, Any]:
    """
    Authenticate a user with username and password.
    
    Args:
        username: The username to authenticate
        password: The password to verify
        
    Returns:
        Dict with 'success' boolean and either 'user_id' or 'error' message
    """
    print("[BANK] Authenticating user: ", username, password)
    user_id = users_by_username.get(username)
    if not user_id:
        print("[BANK] User not found")
        return {"success": False, "error": "User not found"}
    
    user = users_by_id.get(user_id)
    if user and user['password'] == password:
        print("[BANK] User authenticated successfully")
        return {"success": True, "user_id": user_id}
    
    print("[BANK] Invalid password")
    return {"success": False, "error": "Invalid password"}

async def get_balance(user_id: str) -> dict[str, Any] | None:
    user = users_by_id.get(user_id)
    if not user:
        return {}

    balances = {}

    for account in user.get("accounts", []):
        balances[account["account_id"]] = {
            "account_name": account["account_name"],
            "account_type": account["account_type"],
            "balance": account["balance"],
            "available_balance": account["available_balance"],
            "currency": account["currency"],
            "status": account["status"]
        }

    return balances

async def get_account_type(user_id: str) -> dict[str, Any] | None:
    user = users_by_id.get(user_id)
    if not user:
        return {}

    accounts = {}

    for account in user.get("accounts", []):
        accounts[account["account_id"]] = {
            "account_type": account["account_type"],
            "account_name": account["account_name"],
            "currency": account["currency"],
            "status": account["status"]
        }

    return accounts

async def get_user_transactions(user_id: str, limit: int) -> list[str, Any] | None:
    user = users_by_id.get(user_id)
    if not user:
        return []

    transactions = user.get("transactions", [])
    return transactions[-limit:]

async def get_products_eligibility_rules(product_id: str) -> dict[str, Any] | None:
    product = retail_products_by_id.get(product_id)
    if product:
        return product['eligibility']
    return None

async def get_all_products() -> dict[str, Any] | None:
    return retail_products_by_id

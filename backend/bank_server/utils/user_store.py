import json
from pathlib import Path
from typing import Any, Dict, Optional

DATA_FILE = Path(__file__).resolve().parent.parent / "mock_data" / "users.json"


def load_users() -> Dict[str, Any]:
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    users_doc = load_users()
    for user in users_doc.get("users", []):
        if user.get("username") == username:
            return user
    return None

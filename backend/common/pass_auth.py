import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Dict

from jose import JWTError, jwt

from backend.bank_server.utils.auth_config import ALGORITHM, SECRET_KEY, TOKEN_EXPIRE_DELTA


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def verify_password(plain_password: str, password_hash: str, salt: str) -> bool:
    computed = hash_password(plain_password, salt)
    return hmac.compare_digest(computed, password_hash)


def create_access_token(subject: Dict[str, Any]) -> str:
    payload = subject.copy()
    payload["exp"] = datetime.now(timezone.utc) + TOKEN_EXPIRE_DELTA
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

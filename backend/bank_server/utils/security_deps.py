from typing import Optional, Dict, Any
import hmac
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


from .auth_config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AUTH_COOKIE_HTTPONLY,
    AUTH_COOKIE_PREFIX,
    AUTH_COOKIE_SAMESITE,
    AUTH_COOKIE_SECURE,
    CSRF_COOKIE_HTTPONLY,
    CSRF_COOKIE_PREFIX,
    CSRF_HEADER_NAME,
)
from backend.common.pass_auth import create_access_token, decode_token
from .user_store import get_user_by_username


bearer_scheme = HTTPBearer(auto_error=False)


def auth_cookie_name(session_id: str) -> str:
    return f"{AUTH_COOKIE_PREFIX}_{session_id}"


def csrf_cookie_name(session_id: str) -> str:
    return f"{CSRF_COOKIE_PREFIX}_{session_id}"


def refresh_session_cookies(response: Response, user: Dict[str, Any], session_id: str, csrf_token: str) -> None:
    token = create_access_token(
        {"sub": user["username"], "role": user["role"], "sid": session_id}
    )
    response.set_cookie(
        key=auth_cookie_name(session_id),
        value=token,
        httponly=AUTH_COOKIE_HTTPONLY,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key=csrf_cookie_name(session_id),
        value=csrf_token,
        httponly=CSRF_COOKIE_HTTPONLY,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def get_current_user(
    request: Request,
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    request_session_id = request.headers.get("X-Session-Id")
    if not request_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session id",
        )
    token = request.cookies.get(auth_cookie_name(request_session_id))
    if not token and credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    username = payload.get("sub")
    token_session_id = payload.get("sid")

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    if not token_session_id or not request_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session context",
        )
    if not hmac.compare_digest(token_session_id, request_session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session mismatch across tabs",
        )

    user = get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    csrf_token = request.cookies.get(csrf_cookie_name(request_session_id))
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing CSRF session cookie",
        )

    # Sliding inactivity timeout: successful request refreshes both cookies for 5 more minutes.
    refresh_session_cookies(response, user, request_session_id, csrf_token)
    return user


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def verify_csrf(request: Request) -> None:
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )
    csrf_cookie = request.cookies.get(csrf_cookie_name(session_id))
    csrf_header = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_cookie or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )
    if not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed",
        )

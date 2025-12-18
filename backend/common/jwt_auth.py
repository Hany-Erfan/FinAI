"""
Simple JWT-based authentication for microservices.

This module provides stateless authentication across microservices by:
1. Encoding Odoo credentials directly in JWT tokens (no encryption)
2. Allowing each service to independently validate tokens
3. Eliminating shared session state

NOTE: This is a simplified version without encryption. In production,
you should encrypt sensitive data or use HTTPS to protect credentials in transit.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel


# Configuration - Load from environment variables
SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production-min-32-chars"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_EXPIRE_MINUTES", "480")
)  # 8 hours default

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


class User(BaseModel):
    """Model for Odoo credentials"""

    user_id: str


def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token with Odoo credentials.

    :param user_id: User ID
    :type user_id: str
    :param expires_delta: Token expiration time (default: ACCESS_TOKEN_EXPIRE_MINUTES)
    :type expires_delta: Optional[timedelta]
    :return: JWT token string containing the credentials
    :rtype: str
    """
    # Calculate expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # Create JWT payload with all credentials
    payload = {
        "sub": user_id,
        "exp": expire,
    }

    # Encode the payload into a JWT token
    # This signs the token with SECRET_KEY so it can't be tampered with
    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.

    This function:
    1. Checks the token signature (ensures it wasn't tampered with)
    2. Checks the expiration time
    3. Extracts the credentials from the token

    :param token: JWT token string
    :type token: str
    :return: Dictionary containing the decoded credentials
    :rtype: Dict[str, Any]
    :raises HTTPException: If token is invalid, expired, or tampered with
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        print(f"Token: {token}")
        print(f"SECRET_KEY: {SECRET_KEY}")
        print(f"ALGORITHM: {ALGORITHM}")
        # Decode and verify the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Payload: {payload}")

        # Extract credentials from payload
        user_id: str = payload.get("sub")

        # Verify all required fields are present
        if user_id is None:
            raise credentials_exception

        return {
            "user_id": user_id,
            
        }

    except jwt.ExpiredSignatureError:
        # Token has expired
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )



def get_current_user_credentials(
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    FastAPI dependency to extract and validate user_id from JWT token.

    This is used as a dependency in your API endpoints to automatically:
    1. Extract the JWT token from the Authorization header
    2. Verify the token is valid
    3. Extract the user_id
    4. Make them available to your endpoint function

    :param token: JWT token from Authorization header (automatically extracted by FastAPI)
    :type token: str
    :return: User object with user_id
    :rtype: User
    :raises HTTPException: If token is invalid or expired
    """
    # Verify token and extract credentials
    token_data = verify_token(token)

    # Return as User object for easy access
    return User(
        user_id=token_data["user_id"],
    )


def get_token_for_forwarding(token: str = Depends(oauth2_scheme)) -> str:
    """
    FastAPI dependency to get the raw token for forwarding to other services.

    This is useful in the orchestrator when it needs to forward the token
    to specialized agent microservices.

    The function validates the token first to ensure it's valid before forwarding.

    :param token: JWT token from Authorization header
    :type token: str
    :return: The raw token string (after validation)
    :rtype: str
    :raises HTTPException: If token is invalid
    """
    # Validate token first
    verify_token(token)
    # Return the raw token for forwarding
    return token

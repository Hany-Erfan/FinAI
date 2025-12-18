"""
Login route and authentication dependencies.
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
import httpx
import os

from backend.common.jwt_auth import create_access_token, verify_token   
from backend.host_agent.schemas import LoginResponse


router = APIRouter()
security = HTTPBearer()

# Bank server configuration
BANK_URL = os.getenv('BANK_URL', 'http://localhost:8006')


# ---------------------------------------------------------------------
# 🔹 Utility Functions
# ---------------------------------------------------------------------

async def bank_authenticate(username: str, password: str) -> str | None:
    """
    Authenticate with the bank server via HTTP request.
    Returns user_id if authentication succeeds, None otherwise.
    
    Args:
        username: The username to authenticate
        password: The password to verify
        
    Returns:
        user_id if successful, None if authentication fails
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{BANK_URL}/user_auth/authenticate",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("user_id")
            
            return None
    except httpx.RequestError as e:
        print(f"[ERROR] Failed to connect to bank server: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error during bank authentication: {e}")
        return None


def _generate_jwt_token(user_id: str) -> str:
    """Generate a JWT token embedding user credentials for stateless authentication.
    
    Args:
        user_id: User ID
        
    Returns:
        JWT token string
    """
    return create_access_token(
        user_id=user_id,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Verify JWT token and return user info.
    
    Args:
        credentials: The HTTP bearer credentials containing the JWT token
        
    Returns:
        Dictionary containing user information from the JWT token
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        token = credentials.credentials
        payload = verify_token(token)
        return payload
    except Exception as e:
        print(f"[ERROR] Invalid authentication credentials: {e}")
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False))
) -> Dict[str, Any] | None:
    """Verify JWT token and return user info, or None if not authenticated.
    
    Args:
        credentials: The HTTP bearer credentials containing the JWT token (optional)
        
    Returns:
        Dictionary containing user information from the JWT token, or None
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token)
        return payload
    except Exception as e:
        print(f"[WARN] Invalid token in optional auth: {e}")
        return None

@router.post("/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint that authenticates with the bank server and returns a JWT token.
    
    Args:
        form_data: OAuth2 form data containing username and password
        
    Returns:
        LoginResponse with access token and user information
        
    Raises:
        HTTPException: If authentication fails or an error occurs
    """
    user_id = await bank_authenticate(
        form_data.username,
        form_data.password
    )

    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication failed")

    access_token = create_access_token(user_id)

    try:
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=user_id,
            username=form_data.username
        )
    except Exception as e:
        print(f"[ERROR] Unexpected error during login: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during login: {str(e)}")



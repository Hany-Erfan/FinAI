from fastapi import APIRouter
from pydantic import BaseModel
from backend.bank_server.banking_utils import authenticate


class AuthRequest(BaseModel):
    """Request model for authentication"""
    username: str
    password: str


class AuthResponse(BaseModel):
    """Response model for authentication"""
    user_id: str | None
    success: bool
    message: str | None = None


user_auth_router = APIRouter(
    prefix="/user_auth",
    tags=["user_auth"],
    responses={404: {"description": "Not found"}},
)


@user_auth_router.post("/authenticate", response_model=AuthResponse)
async def authenticate_endpoint(auth_request: AuthRequest) -> AuthResponse:
    """
    Authenticate a user with username and password.
    
    Returns user_id if authentication is successful, otherwise returns error.
    """
    result = await authenticate(auth_request.username, auth_request.password)
    
    if result["success"]:
        return AuthResponse(
            user_id=result["user_id"],
            success=True,
            message="Authentication successful"
        )
    else:
        return AuthResponse(
            user_id=None,
            success=False,
            message=result.get("error", "Authentication failed")
        )
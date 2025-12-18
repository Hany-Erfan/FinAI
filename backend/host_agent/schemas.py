"""
Pydantic schemas for API request/response models.
"""
from pydantic import BaseModel
from typing import Optional


class ChatMessage(BaseModel):
    """Request model for chat messages."""
    message: str
    # Optional media payload (data URL base64 without the prefix, or raw base64)
    media_base64: Optional[str] = None
    media_mime: Optional[str] = None
    media_name: Optional[str] = None
    # 'image' | 'video'
    media_kind: Optional[str] = None
    # Optional session ID for context continuity
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str
    status: str = "completed"


class LoginResponse(BaseModel):
    """Response model for login."""
    access_token: str
    token_type: str
    user_id: str
    username: str


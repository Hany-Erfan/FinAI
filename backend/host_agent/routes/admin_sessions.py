"""Admin-only endpoints for browsing chat sessions, messages, and summaries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.bank_server.utils.security_deps import require_admin
from backend.common.masking_pii import DataMasker
from backend.postgres_db.database import get_db
from backend.postgres_db.repository import SessionRepository

router = APIRouter(prefix="/admin", tags=["Admin Sessions"])


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class SessionListItem(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    status: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int
    has_summary: bool

    model_config = {"from_attributes": True}


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SummaryItem(BaseModel):
    summary_text: str
    key_topics: list[str]
    sentiment: Optional[str] = None
    resolution_status: str
    generated_at: datetime
    model_used: Optional[str] = None

    model_config = {"from_attributes": True}


class SessionDetail(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    status: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    messages: list[MessageItem]
    summary: Optional[SummaryItem] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def _get_repo(db=Depends(get_db)) -> SessionRepository:
    return SessionRepository(db=db, masker=DataMasker())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[SessionListItem])
def list_sessions(
    _admin=Depends(require_admin),
    repo: SessionRepository = Depends(_get_repo),
):
    """Return every session with message count and summary flag."""
    sessions = repo.list_sessions()
    return [
        SessionListItem(
            id=str(s.id),
            user_id=s.user_id,
            user_name=s.user_name,
            status=s.status.value,
            created_at=s.created_at,
            ended_at=s.ended_at,
            message_count=len(s.messages),
            has_summary=s.summary is not None,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session_detail(
    session_id: uuid.UUID,
    _admin=Depends(require_admin),
    repo: SessionRepository = Depends(_get_repo),
):
    """Return full session detail: metadata, messages, and summary."""
    session = repo.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    messages = [
        MessageItem(
            id=str(m.id),
            role=m.role.value,
            content=m.content,
            created_at=m.created_at,
        )
        for m in session.messages
    ]

    summary = None
    if session.summary:
        s = session.summary
        summary = SummaryItem(
            summary_text=s.summary_text,
            key_topics=s.key_topics or [],
            sentiment=s.sentiment,
            resolution_status=s.resolution_status.value,
            generated_at=s.generated_at,
            model_used=s.model_used,
        )

    return SessionDetail(
        id=str(session.id),
        user_id=session.user_id,
        user_name=session.user_name,
        status=session.status.value,
        created_at=session.created_at,
        ended_at=session.ended_at,
        messages=messages,
        summary=summary,
    )

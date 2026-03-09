"""
SessionRepository – all DB read/write operations for sessions,
messages, and summaries. Keeps SQL concerns out of agent logic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session as DBSession
from sqlalchemy.dialects.postgresql import insert

from backend.common.masking_pii import DataMasker
from .models import (
    Message, MessageRole, ResolutionStatus,
    Session, SessionStatus, Summary,
)


class SessionRepository:
    def __init__(self, db: DBSession, masker: DataMasker):
        self.db = db
        self.masker: DataMasker = masker if masker is not None else DataMasker()

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def create_session(
        self,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        metadata: Optional[dict] = None,
        session_id: Optional[uuid.UUID] = None,  # pass your existing session ID
    ) -> Session:
        
        session = (
        insert(Session)
        .values(
            id=session_id or uuid.uuid4(),
            user_id=user_id,
            user_name=user_name,
            status=SessionStatus.ACTIVE,
            metadata_=metadata or {},
        ).on_conflict_do_nothing(index_elements=["id"])
        )
        self.db.execute(session)
        self.db.commit()

        return self.db.get(Session, session_id)

    def end_session(self, session_id: uuid.UUID, status: SessionStatus = SessionStatus.ENDED) -> Session:
        session = self._get_session_or_raise(session_id)
        session.status = status
        session.ended_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: uuid.UUID) -> Optional[Session]:
        return self.db.get(Session, session_id)

    def list_sessions(self) -> list[Session]:
        return self.db.query(Session).order_by(Session.created_at.desc()).all()

    # ------------------------------------------------------------------
    # Message CRUD
    # ------------------------------------------------------------------

    def save_message(
        self,
        session_id: uuid.UUID,
        role: MessageRole,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            metadata_=metadata or {},
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_messages(self, session_id: uuid.UUID) -> list[Message]:
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at)
            .all()
        )

    # ------------------------------------------------------------------
    # Summary CRUD
    # ------------------------------------------------------------------

    def save_summary(
        self,
        session_id: uuid.UUID,
        summary_text: str,
        key_topics: list[str],
        sentiment: str,
        resolution_status: ResolutionStatus,
        model_used: str,
        raw_response: Optional[str] = None,
    ) -> Summary:
        # Upsert: replace if already exists
        existing = self.db.query(Summary).filter_by(session_id=session_id).first()
        if existing:
            existing.summary_text = summary_text
            existing.key_topics = key_topics
            existing.sentiment = sentiment
            existing.resolution_status = resolution_status
            existing.model_used = model_used
            existing.raw_response = raw_response or ''
            existing.generated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        summary = Summary(
            session_id=session_id,
            summary_text=summary_text,
            key_topics=key_topics,
            sentiment=sentiment,
            resolution_status=resolution_status,
            model_used=model_used,
            raw_response=raw_response or {},
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        return summary

    def get_summary(self, session_id: uuid.UUID) -> Optional[Summary]:
        return self.db.query(Summary).filter_by(session_id=session_id).first()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_session_or_raise(self, session_id: uuid.UUID) -> Session:
        session = self.db.get(Session, session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        return session
    

    def get_active_session_id(self, user_id: Optional[str] = None) -> Optional[uuid.UUID]:
        """
        Return the UUID of the most-recent ACTIVE session.

        Behavior:
        - If `user_id` is provided: return the most-recent ACTIVE
          session for that customer.
        - If `user_id` is None: return the last-created ACTIVE
          session (optionally filtered by `channel`).

        Returns `None` if no matching active session exists.
        """
        query = self.db.query(Session).filter(Session.status == SessionStatus.ACTIVE)
        
        if user_id is not None:
            query = query.filter(Session.user_id == user_id)

        # When user_id is provided prefer most-recent activity; when
        # searching globally prefer most-recently created session per user
        # request "last created session" — use `created_at` ordering.
        order_field = Session.last_activity_at.desc() if user_id is not None else Session.created_at.desc()

        session = query.order_by(order_field).first()

        return session.id if session is not None else None
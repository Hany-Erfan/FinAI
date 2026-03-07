"""
SQLAlchemy ORM models.

Tables:
  sessions   – one row per session
  messages   – one row per turn (user or model)
  summaries  – one row per session, generated on-demand or at session end
"""
import uuid

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey,
    String, Text, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"
    ESCALATED = "escalated" # currently not used, for later

class MessageRole(str, enum.Enum):
    USER = "user"
    MODEL = "agent"


class ResolutionStatus(str, enum.Enum): # currently not used
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    ESCALATED = "escalated"
    UNKNOWN = "unknown"


class Session(Base):
    """One row per session."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=True, index=True)    
    user_name = Column(String(255), nullable=True)              
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)             # any extra context

    messages = relationship("Message", back_populates="session",
                            cascade="all, delete-orphan", order_by="Message.created_at")
    summary = relationship("Summary", back_populates="session",
                           uselist=False, cascade="all, delete-orphan")


class Message(Base):
    """One row per conversation turn."""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)             # tool calls, citations …

    session = relationship("Session", back_populates="messages")


class Summary(Base):
    """
    AI-generated summary of a completed session.
    Generated either at session end or on demand via export.
    """
    __tablename__ = "summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"),
                        nullable=False, unique=True, index=True)
    summary_text = Column(Text, nullable=False)
    key_topics = Column(JSONB, default=list)                        # ["onbaording", "deposits", …]
    sentiment = Column(String(32), nullable=True)                   # positive / neutral / negative (later)
    resolution_status = Column(Enum(ResolutionStatus),
                                default=ResolutionStatus.UNKNOWN, nullable=False) # later
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    model_used = Column(String(128), nullable=True)                 # gemini model version
    raw_response = Column(JSONB, default=dict)                      # full structured output

    session = relationship("Session", back_populates="summary")

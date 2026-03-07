from http.client import HTTPException
import uuid

from pydantic import BaseModel

from backend.common.masking_pii import DataMasker
from backend.postgres_db.database import get_db

from fastapi import APIRouter, Depends
from typing import List
from backend.postgres_db.repository import SessionRepository

messages_information_router = APIRouter(
    tags=["messages_information"],
)
class Message(BaseModel):
  text: str
  sender: str
  timestamp: str


def _serialize_message(msg) -> Message:
    return Message(
        sender=msg.role.value if hasattr(msg.role, "value") else str(msg.role),
        text=msg.content,
        timestamp=msg.created_at.isoformat() if msg.created_at is not None else None,
    )


@messages_information_router.get("/sessions/{session_id}/messages", response_model=List[Message])
def get_messages(session_id: uuid.UUID, db=Depends(get_db)):
    masker = DataMasker()
    repo = SessionRepository(db, masker)
    try:
        messages = repo.get_messages(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return [_serialize_message(m) for m in messages]
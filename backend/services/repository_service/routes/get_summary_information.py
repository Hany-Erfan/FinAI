from http.client import HTTPException
import logging
import uuid

from pydantic import BaseModel

from backend.common.masking_pii import DataMasker
from backend.postgres_db.database import get_db
from backend.postgres_db.models import ResolutionStatus

from fastapi import APIRouter, Depends
from typing import List, Optional
from backend.postgres_db.repository import SessionRepository

summary_information_router = APIRouter(
    tags=["summary_information"],
)

class SummaryPayload(BaseModel):
    summary_text: str
    key_topics: List[str]
    sentiment: str
    resolution_status: str
    model_used: str
    raw_response: Optional[str] = None

@summary_information_router.post("/sessions/{session_id}/save_summaries", response_model=dict)
def save_summary(session_id: str, payload: SummaryPayload, db=Depends(get_db)):
    masker = DataMasker()
    repo = SessionRepository(db, masker)
    try:
        try:
            resolution = ResolutionStatus(payload.resolution_status)
        except Exception:
            # attempt case-insensitive match
            try:
                resolution = ResolutionStatus(payload.resolution_status.lower())
            except Exception:
                raise HTTPException(status_code=400, detail="invalid resolution_status")

        summary = repo.save_summary(
            session_id=session_id,
            summary_text=payload.summary_text,
            key_topics=payload.key_topics,
            sentiment=payload.sentiment,
            resolution_status=resolution,
            model_used=payload.model_used,
            raw_response=payload.raw_response,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "id": str(summary.id),
        "session_id": str(summary.session_id),
        "generated_at": summary.generated_at.isoformat() if summary.generated_at else None,
    }




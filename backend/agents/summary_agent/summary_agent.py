"""
SummaryAgent (Google ADK variant) – identical public interface to
summary_agent.py but implemented with the Google Agent Development Kit.

Key difference vs. the plain genai version
-------------------------------------------
Plain genai:  prompt asks Gemini to output JSON text → we parse/regex it.
              Fragile: model can add markdown fences, trailing text, etc.

ADK:          we define a `record_summary` *tool* (a Python function).
              The ADK Agent is instructed to analyse the transcript and
              CALL that tool with the structured fields as parameters.
              No JSON parsing. No regex. The function signature IS the
              schema that Gemini must conform to via native function calling.

ADK session note
-----------------
ADK has its own session/memory concept (InMemorySessionService), which is
separate from our PostgreSQL conversation sessions. Each call to
`generate_and_store()` creates a short-lived ADK session just for that
single summarisation task, then discards it. Our DB is still the source
of truth for all persistent state.

Masking
-------
A two-layer strategy: transcript is masked
before being sent to the ADK agent, guarding against any content that
bypassed ChatAgent's first-pass masking.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Optional
from fastapi import Depends
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
)
from google.adk.agents import LlmAgent

from backend.common.cache_dict import SummaryAgentCache
from backend.common.masking_pii import DataMasker
from backend.postgres_db.models import ResolutionStatus
from backend.postgres_db.repository import SessionRepository

# ---------------------------------------------------------------------------
# ADK agent instruction
# ---------------------------------------------------------------------------
AGENT_INSTRUCTION = """\
You are an expert customer service analyst.
You will receive a masked conversation transcript (PII has been replaced
with placeholders like <EMAIL_1>).

Your job is to analyse the transcript and call the `record_summary` tool
EXACTLY ONCE with the following fields:
  - summary_text      : a concise 2-4 sentence prose summary
  - key_topics        : list of short topic strings (e.g. ["billing","refund"])
  - sentiment         : one of  positive | neutral | negative
  - resolution_status : one of  resolved | unresolved | escalated | unknown

Do not output any other text. Call the tool and stop.
"""

APP_NAME = "summary_agent"

def create_summary_agent() -> LlmAgent:
    """Constructs the ADK agent."""
    return LlmAgent(
            name="summary_agent",
            model="gemini-3-flash-preview",
            description="Analyses the whole transcript and records structured summaries.",
            instruction=AGENT_INSTRUCTION,
            tools=[
            MCPToolset(
                connection_params=StdioServerParameters(
                    command='python',
                    args=['backend/agents/summary_agent/summary_mcp.py'],
                    env=dict(os.environ),
                ),
            )
        ],
        )

class SummaryAgent:
    def __init__(self, repo: SessionRepository, masker: Optional[DataMasker] = None):
        self.repo = repo
        self.masker: DataMasker = masker if masker is not None else DataMasker()
        google_agent = create_summary_agent()

        # Initialize base class
        super().__init__(
            app_name=APP_NAME,
            google_agent=google_agent,
        )

    @classmethod
    def get_agent(cls, user_id: str) -> "SummaryAgent":
        """Return a cached or new Summary agent instance.

        :param user_id: Cache key for the user
        :type user_id: str
        :return: FAQAgent instance
        :rtype: FAQAgent
        """
        if user_id not in SummaryAgentCache:
            print(f"[Summary] Creating new agent instance for user {user_id}")
            SummaryAgentCache[user_id] = cls(user_id)
        else:
            print(f"[Summary] Using cached agent instance for user {user_id}")
        
        return SummaryAgentCache[user_id]
    
    @classmethod
    def generate_and_store(cls, session_id: uuid.UUID) -> dict:
        """
        Run the ADK agent over the session transcript, capture the
        structured tool call result, and persist it to the DB.
        """

        messages = cls.repo.get_messages(session_id)
        if not messages:
            raise ValueError(f"Session {session_id} has no messages to summarise.")

        transcript = build_transcript(messages)
        safe_transcript = cls.repo.masker.mask(transcript)
        print('safe transcript ', safe_transcript)
        # Run the ADK agent synchronously (wraps the async runner)
        #parsed = await self.run(safe_transcript)

        resolution = ResolutionStatus(safe_transcript.get("resolution_status", "unknown"))
        cls.repo.save_summary(
            session_id=session_id,
            summary_text=safe_transcript["summary_text"],
            key_topics=safe_transcript["key_topics"],
            sentiment=safe_transcript["sentiment"],
            resolution_status=resolution,
            model_used="gemini-3-flash-preview",
            raw_response=safe_transcript,
        )
        return safe_transcript

""" def export_session(session_id: uuid.UUID, repo: SessionRepository, triggered_by: str = "manual") -> dict:
    session = repo.get_session(session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found.")

    summary = repo.get_summary(session_id)
    if summary is None:
        generate_and_store(session_id)
        summary = repo.get_summary(session_id)

    messages = repo.get_messages(session_id)

    session_info = {
        "id": str(session.id),
        "customer_id": session.customer_id,
        "customer_name": session.customer_name,
        "status": session.status.value,
        "created_at": session.created_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }
        
    messages_payload = [
        {
            "role": m.role.value,
            "content": m.content,  # already masked
            "created_at": m.created_at.isoformat(),
        }
            for m in messages
    ]
    summary_info = {
        "summary_text": summary.summary_text,
        "key_topics": summary.key_topics,
        "sentiment": summary.sentiment,
        "resolution_status": summary.resolution_status.value,
        "generated_at": summary.generated_at.isoformat(),
        "model_used": summary.model_used,
    }

    repo.save_export(
        session_id=session_id,
        session_info=session_info,
        messages=messages_payload,
        summary_info=summary_info,
        triggered_by=triggered_by,
    )

    return {"session": session_info, "messages": messages_payload, "summary": summary_info}
"""
# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def build_transcript(messages) -> str:
    return "\n".join(
        f"[{m.role.value.upper()}]: {m.content}" for m in messages
    ) 
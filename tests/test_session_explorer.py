"""
Tests for the Session Explorer admin endpoints.

Covers:
  - GET /admin/sessions  (list sessions — admin vs user vs unauthenticated)
  - GET /admin/sessions/{id}  (session detail — admin, 404, user/unauth)
"""

import uuid
import pytest
import pytest_asyncio
import httpx
import os

HOST_AGENT_URL = os.getenv("HOST_AGENT_URL", "http://localhost:8000")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin_AgentixBuddy"
USER_USERNAME = "user"
USER_PASSWORD = "user_AgentixBuddy"


class TestSessionExplorer:
    """Test suite for Session Explorer admin endpoints."""

    # ---- fixtures ----

    @pytest_asyncio.fixture
    async def admin_session(self):
        """Login as admin, return cookies + session_id."""
        session_id = str(uuid.uuid4())
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{HOST_AGENT_URL}/login",
                json={
                    "username": ADMIN_USERNAME,
                    "password": ADMIN_PASSWORD,
                    "session_id": session_id,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["role"] == "admin"
            return {"cookies": resp.cookies, "session_id": session_id}

    @pytest_asyncio.fixture
    async def user_session(self):
        """Login as regular user, return cookies + session_id."""
        session_id = str(uuid.uuid4())
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{HOST_AGENT_URL}/login",
                json={
                    "username": USER_USERNAME,
                    "password": USER_PASSWORD,
                    "session_id": session_id,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["role"] == "user"
            return {"cookies": resp.cookies, "session_id": session_id}

    # ---- GET /admin/sessions ----

    @pytest.mark.asyncio
    async def test_list_sessions_without_auth(self):
        """Unauthenticated request to /admin/sessions → 401."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{HOST_AGENT_URL}/admin/sessions")
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_sessions_as_regular_user(self, user_session):
        """Regular user → 403 Forbidden."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HOST_AGENT_URL}/admin/sessions",
                headers={"X-Session-Id": user_session["session_id"]},
                cookies=user_session["cookies"],
            )
            assert resp.status_code == 403
            assert resp.json()["detail"] == "Admin role required"

    @pytest.mark.asyncio
    async def test_list_sessions_as_admin(self, admin_session):
        """Admin → 200 with a list of sessions."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HOST_AGENT_URL}/admin/sessions",
                headers={"X-Session-Id": admin_session["session_id"]},
                cookies=admin_session["cookies"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            # The admin_session fixture itself created a session via /login,
            # so there must be at least one session
            assert len(data) >= 1
            # Verify shape of the first item
            first = data[0]
            assert "id" in first
            assert "status" in first
            assert "created_at" in first
            assert "message_count" in first
            assert "has_summary" in first

    # ---- GET /admin/sessions/{id} ----

    @pytest.mark.asyncio
    async def test_session_detail_without_auth(self):
        """Unauthenticated request to detail → 401."""
        fake_id = str(uuid.uuid4())
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HOST_AGENT_URL}/admin/sessions/{fake_id}"
            )
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_session_detail_as_regular_user(self, user_session):
        """Regular user → 403 Forbidden."""
        fake_id = str(uuid.uuid4())
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HOST_AGENT_URL}/admin/sessions/{fake_id}",
                headers={"X-Session-Id": user_session["session_id"]},
                cookies=user_session["cookies"],
            )
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_session_detail_not_found(self, admin_session):
        """Admin requests non-existent session → 404."""
        fake_id = str(uuid.uuid4())
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HOST_AGENT_URL}/admin/sessions/{fake_id}",
                headers={"X-Session-Id": admin_session["session_id"]},
                cookies=admin_session["cookies"],
            )
            assert resp.status_code == 404
            assert resp.json()["detail"] == "Session not found"

    @pytest.mark.asyncio
    async def test_session_detail_as_admin(self, admin_session):
        """Admin fetches the session created by the admin_session fixture."""
        async with httpx.AsyncClient() as client:
            # The admin login created a session with this session_id
            resp = await client.get(
                f"{HOST_AGENT_URL}/admin/sessions/{admin_session['session_id']}",
                headers={"X-Session-Id": admin_session["session_id"]},
                cookies=admin_session["cookies"],
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == admin_session["session_id"]
            assert data["status"] in ("active", "ended", "escalated")
            assert isinstance(data["messages"], list)
            # summary may or may not exist
            assert "summary" in data

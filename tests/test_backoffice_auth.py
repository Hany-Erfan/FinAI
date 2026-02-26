import pytest
import pytest_asyncio
import httpx
import os

# Base URLs for services
HOST_AGENT_URL = os.getenv("HOST_AGENT_URL", "http://localhost:8000")
VECTOR_DB_URL = os.getenv("VECTOR_DB_URL", "http://localhost:8004")

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin_AgentixBuddy"
USER_USERNAME = "user"
USER_PASSWORD = "user_AgentixBuddy"


class TestBackofficeAuth:
    """Test suite for backoffice authentication and authorization."""

    @pytest_asyncio.fixture
    async def admin_session(self):
        """Login as admin and return session cookies and session_id."""
        session_id = "test-admin-session-integration"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HOST_AGENT_URL}/login",
                json={
                    "username": ADMIN_USERNAME,
                    "password": ADMIN_PASSWORD,
                    "session_id": session_id
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["role"] == "admin"
            return {
                "cookies": response.cookies,
                "session_id": session_id
            }

    @pytest_asyncio.fixture
    async def user_session(self):
        """Login as regular user and return session cookies and session_id."""
        session_id = "test-user-session-integration"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HOST_AGENT_URL}/login",
                json={
                    "username": USER_USERNAME,
                    "password": USER_PASSWORD,
                    "session_id": session_id
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["role"] == "user"
            return {
                "cookies": response.cookies,
                "session_id": session_id
            }

    @pytest.mark.asyncio
    async def test_login_admin_success(self):
        """Test that admin can login successfully."""
        session_id = "test-login-admin"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HOST_AGENT_URL}/login",
                json={
                    "username": ADMIN_USERNAME,
                    "password": ADMIN_PASSWORD,
                    "session_id": session_id
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Login successful"
            assert data["role"] == "admin"
            assert data["username"] == ADMIN_USERNAME

    @pytest.mark.asyncio
    async def test_login_user_success(self):
        """Test that regular user can login successfully."""
        session_id = "test-login-user"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HOST_AGENT_URL}/login",
                json={
                    "username": USER_USERNAME,
                    "password": USER_PASSWORD,
                    "session_id": session_id
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Login successful"
            assert data["role"] == "user"
            assert data["username"] == USER_USERNAME

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Test that invalid credentials are rejected."""
        session_id = "test-login-invalid"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HOST_AGENT_URL}/login",
                json={
                    "username": "invalid_user",
                    "password": "wrong_password",
                    "session_id": session_id
                }
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_backoffice_products_without_auth(self):
        """Test that products endpoint rejects unauthenticated requests."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{VECTOR_DB_URL}/vector_db_service/products"
            )
            assert response.status_code == 401
            data = response.json()
            assert data["detail"] == "Missing session id"

    @pytest.mark.asyncio
    async def test_backoffice_products_with_admin(self, admin_session):
        """Test that admin can access products endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{VECTOR_DB_URL}/vector_db_service/products",
                headers={"X-Session-Id": admin_session["session_id"]},
                cookies=admin_session["cookies"]
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "products" in data

    @pytest.mark.asyncio
    async def test_backoffice_products_with_regular_user(self, user_session):
        """Test that regular user cannot access products endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{VECTOR_DB_URL}/vector_db_service/products",
                headers={"X-Session-Id": user_session["session_id"]},
                cookies=user_session["cookies"]
            )
            assert response.status_code == 403
            data = response.json()
            assert data["detail"] == "Admin role required"

    @pytest.mark.asyncio
    async def test_backoffice_upsert_without_auth(self):
        """Test that upsert endpoint rejects unauthenticated requests."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VECTOR_DB_URL}/vector_db_service/upsert",
                json={
                    "category": "test",
                    "question_en": "Test question?",
                    "answer_en": "Test answer.",
                    "question_ar": "",
                    "answer_ar": ""
                }
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_backoffice_upsert_with_regular_user(self, user_session):
        """Test that regular user cannot upsert products."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VECTOR_DB_URL}/vector_db_service/upsert",
                headers={"X-Session-Id": user_session["session_id"]},
                cookies=user_session["cookies"],
                json={
                    "category": "test",
                    "question_en": "Test question?",
                    "answer_en": "Test answer.",
                    "question_ar": "",
                    "answer_ar": ""
                }
            )
            assert response.status_code == 403
            data = response.json()
            assert data["detail"] == "Admin role required"

    @pytest.mark.asyncio
    async def test_backoffice_delete_without_auth(self):
        """Test that delete endpoint rejects unauthenticated requests."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{VECTOR_DB_URL}/vector_db_service/delete/test-product-id"
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_backoffice_delete_with_regular_user(self, user_session):
        """Test that regular user cannot delete products."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{VECTOR_DB_URL}/vector_db_service/delete/test-product-id",
                headers={"X-Session-Id": user_session["session_id"]},
                cookies=user_session["cookies"]
            )
            assert response.status_code == 403
            data = response.json()
            assert data["detail"] == "Admin role required"

    @pytest.mark.asyncio
    async def test_backoffice_clear_without_auth(self):
        """Test that clear endpoint rejects unauthenticated requests."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{VECTOR_DB_URL}/vector_db_service/clear"
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_backoffice_clear_with_regular_user(self, user_session):
        """Test that regular user cannot clear all products."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{VECTOR_DB_URL}/vector_db_service/clear",
                headers={"X-Session-Id": user_session["session_id"]},
                cookies=user_session["cookies"]
            )
            assert response.status_code == 403
            data = response.json()
            assert data["detail"] == "Admin role required"

    @pytest.mark.asyncio
    async def test_backoffice_upload_without_auth(self):
        """Test that upload endpoint rejects unauthenticated requests."""
        async with httpx.AsyncClient() as client:
            # Create a minimal fake xlsx file content for testing
            response = await client.post(
                f"{VECTOR_DB_URL}/vector_db_service/upload",
                files={"file": ("test.xlsx", b"fake content", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_backoffice_upload_with_regular_user(self, user_session):
        """Test that regular user cannot upload files."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VECTOR_DB_URL}/vector_db_service/upload",
                headers={"X-Session-Id": user_session["session_id"]},
                cookies=user_session["cookies"],
                files={"file": ("test.xlsx", b"fake content", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
            assert response.status_code == 403
            data = response.json()
            assert data["detail"] == "Admin role required"

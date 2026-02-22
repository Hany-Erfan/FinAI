import pytest
import httpx
import asyncio
import os

# Base URLs for services (using localhost for local testing, can be overridden by env vars in CI)
HOST_AGENT_URL = os.getenv("HOST_AGENT_URL", "http://localhost:8000")
FAQ_AGENT_URL = os.getenv("FAQ_AGENT_URL", "http://localhost:8001")
RETAIL_AGENT_URL = os.getenv("RETAIL_AGENT_URL", "http://localhost:8002")
BANK_SERVER_URL = os.getenv("BANK_SERVER_URL", "http://localhost:8006")
VECTOR_DB_URL = os.getenv("VECTOR_DB_URL", "http://localhost:8004")

@pytest.mark.asyncio
async def test_host_agent_health():
    async with httpx.AsyncClient() as client:
        # Check root or docs or a known endpoint
        response = await client.get(f"{HOST_AGENT_URL}/docs")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_faq_agent_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FAQ_AGENT_URL}/docs")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_retail_agent_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{RETAIL_AGENT_URL}/docs")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_bank_server_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BANK_SERVER_URL}/docs")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_vector_db_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{VECTOR_DB_URL}/docs")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_cross_service_login_attempt():
    """
    Test a basic login attempt on the host agent.
    This verifies the host agent can at least start up and handle routes.
    """
    async with httpx.AsyncClient() as client:
        # Host agent has a login_router
        # Let's try to ping the login endpoint
        response = await client.post(f"{HOST_AGENT_URL}/login", json={"username": "test", "password": "test"})
        # We expect a 401 or 400 if credentials are wrong, but 200/401 is better than 500 or ConnectionError
        assert response.status_code in [200, 401, 400]

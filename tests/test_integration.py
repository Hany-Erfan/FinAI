import pytest
import httpx
import asyncio
import os

# Base URLs for services (using localhost for local testing, can be overridden by env vars in CI)
HOST_AGENT_URL = os.getenv("HOST_AGENT_URL", "http://localhost:8000")
FAQ_AGENT_URL = os.getenv("FAQ_AGENT_URL", "http://localhost:8001")
RETAIL_AGENT_URL = os.getenv("RETAIL_AGENT_URL", "http://localhost:8002")
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
        # Agents use Starlette and have a /health route
        response = await client.get(f"{FAQ_AGENT_URL}/health")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_retail_agent_health():
    async with httpx.AsyncClient() as client:
        # Agents use Starlette and have a /health route
        response = await client.get(f"{RETAIL_AGENT_URL}/health")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_vector_db_health():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{VECTOR_DB_URL}/docs")
        assert response.status_code == 200

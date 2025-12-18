from fastapi import APIRouter
from datetime import datetime, timezone

vector_db_health_router = APIRouter(
    prefix="/vector_db_service",
    tags=["vector_db_health"],
    responses={404: {"description": "Not found"}},
)


@vector_db_health_router.get("/health")
async def get_vector_db_health():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "health check API",
    }


from datetime import datetime, timezone
from fastapi import APIRouter
from starlette.responses import JSONResponse

voice_health_router = APIRouter(
    prefix="/voice_service",
    tags=["voice_health"],
)

@voice_health_router.get("/health")
async def get_voice_health():
    """Basic health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "voice service API",
    })

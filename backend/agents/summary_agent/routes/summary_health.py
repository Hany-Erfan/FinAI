from datetime import datetime, timezone
from starlette.responses import JSONResponse


async def get_summary_health(request):
    """Basic health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "health check API",
    })



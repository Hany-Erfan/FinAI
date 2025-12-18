from datetime import datetime, timezone


async def get_faq_health():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "health check API",
    }



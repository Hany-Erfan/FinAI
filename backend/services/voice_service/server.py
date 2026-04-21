from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.services.voice_service.routes.voice_health import voice_health_router
from backend.services.voice_service.routes.stt import stt_router
from backend.services.voice_service.routes.tts import tts_router

def build_voice_app():
    """Build and return the Voice Service FastAPI application"""
    app = FastAPI(title="Voice Service API")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(voice_health_router)
    app.include_router(stt_router)
    app.include_router(tts_router)
    
    return app

voice_db_app = build_voice_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.services.voice_service.server:voice_db_app",
        host="0.0.0.0",
        port=8008,
        reload=True,
        log_level="debug",
        use_colors=True
    )

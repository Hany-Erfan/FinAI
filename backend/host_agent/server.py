"""
Host Agent A2A Server
HTTP bridge that connects frontend to A2A host agent
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.host_agent.routes import chat_router, login_router

# FastAPI app for HTTP endpoints
app = FastAPI(
    title="Host Agent HTTP Bridge",
    description="HTTP bridge to A2A host agent",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(login_router, tags=["login"])
app.include_router(chat_router, tags=["Chat"])

def main():
    """Main function to start the host agent server"""
    print("[START] Starting Host Agent A2A Server...")
    print("[HTTP] HTTP Bridge: http://localhost:8083")
    print("[SERVER] Starting server...")

    import uvicorn

    uvicorn.run(
        "backend.host_agent.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()

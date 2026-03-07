from backend.services.repository_service.routes.get_summary_information import summary_information_router
from backend.services.repository_service.routes.get_messages import messages_information_router

import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

repository_app = FastAPI(
    title="Repository Service",
    description="A service for calling the database repository over MCP in summary_agent",
    version="0.1.0",
)

# Add CORS middleware to allow cross-origin requests
repository_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
routers = [
    summary_information_router,
    messages_information_router
]

for router in routers:
    repository_app.include_router(router)

if __name__ == "__main__":
    host = os.getenv("REPOSITORY_HOST", "0.0.0.0")
    port = int(os.getenv("REPOSITORY_PORT", "8007"))
    uvicorn.run(
        "backend.services.repository_service.server:repository_app", host=host, port=port, reload=True
    )
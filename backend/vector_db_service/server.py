import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.vector_db_service.routes.vector_db_health import vector_db_health_router
from backend.vector_db_service.routes.retreive_product import retreive_product_router
from backend.vector_db_service.routes.manage_documents import manage_documents_router

vector_db_app = FastAPI(
    title="Vector DB Service",
    description="A service for Product RAG",
    version="0.1.0",
)

# Add CORS middleware to allow cross-origin requests
vector_db_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
routers = [
    vector_db_health_router,
    retreive_product_router,
    manage_documents_router,
]

for router in routers:
    vector_db_app.include_router(router)

if __name__ == "__main__":
    host = os.getenv("VECTOR_DB_HOST", "0.0.0.0")
    port = int(os.getenv("VECTOR_DB_PORT", "8004"))
    uvicorn.run(
        "backend.vector_db_service.server:vector_db_app", host=host, port=port, reload=True
    )
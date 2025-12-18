import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.vector_db_service.routes.vector_db_health import vector_db_health_router
from backend.vector_db_service.routes.retreive_product import retreive_product_router
# from backend.common.observability import get_langfuse_client, instrument_google_adk

# langfuse = get_langfuse_client()
# instrument_google_adk()

vector_db_app = FastAPI(
    title="Vector DB Service",
    description="A service for RAG",
    version="1.0.0",
)

# CORS middleware
vector_db_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

routers = [
    vector_db_health_router,
    retreive_product_router,
]

for router in routers:
    vector_db_app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        "backend.vector_db_service.server:vector_db_app", host="0.0.0.0", port=8004, reload=True
    )
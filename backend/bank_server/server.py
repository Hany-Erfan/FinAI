from fastapi import FastAPI
import uvicorn
from backend.bank_server.routes.get_user_data import user_information_router
from backend.bank_server.routes.get_products_data import product_information_router
from backend.bank_server.routes.user_auth import user_auth_router
from observability import setup_telemetry, setup_logging, instrument_app

bank_app = FastAPI(title="Banking API", description="Banking API", version="1.0.0")
instrument_app(bank_app)

@bank_app.on_event("startup")
async def startup_event():
    setup_telemetry()
    setup_logging()

routers = [user_information_router, product_information_router, user_auth_router]

for router in routers:
    bank_app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.bank_server.server:bank_app",
        host="0.0.0.0",
        port=8006,
        reload=True,
    )

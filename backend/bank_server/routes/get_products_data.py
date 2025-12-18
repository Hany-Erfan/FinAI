from fastapi import APIRouter
from typing import Dict, Any
from backend.bank_server.banking_utils import get_all_products, get_products_eligibility_rules


product_information_router = APIRouter(
    prefix="/product_information",
    tags=["product_information"],
    responses={404: {"description": "Not found"}},
)

@product_information_router.get("/get_all_products", response_model=Dict[str, Any])
async def get_all_products_endpoint():
    return await get_all_products()

@product_information_router.get("/get_products_eligibility_rules/{product_id}", response_model=Dict[str, Any])
async def get_products_eligibility_rules_endpoint(product_id: str):
    return await get_products_eligibility_rules(product_id)



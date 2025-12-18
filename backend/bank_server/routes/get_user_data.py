from fastapi import APIRouter
from typing import Dict, Any
from backend.bank_server.banking_utils import get_balance, get_account_type, get_user_transactions


user_information_router = APIRouter(
    prefix="/user_information",
    tags=["user_information"],
    responses={404: {"description": "Not found"}},
)

@user_information_router.get("/get_balance/{user_id}", response_model=Dict[str, Any])
async def get_balance_endpoint(user_id: str):
    return await get_balance(user_id)

@user_information_router.get("/get_account_type/{user_id}", response_model=Dict[str, Any])
async def get_account_type_endpoint(user_id: str):
    return await get_account_type(user_id)

@user_information_router.get("/get_transactions/{user_id}")
async def get_user_transactions_endpoint(user_id:str, limit:int):
    return await get_user_transactions(user_id, limit)



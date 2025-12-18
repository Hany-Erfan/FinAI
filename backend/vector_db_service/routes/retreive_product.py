from fastapi import APIRouter
from backend.vector_db_service.store_products import retrieve_documents

retreive_product_router = APIRouter(
    prefix="/vector_db_service",
    tags=["retreive_product"],
    responses={404: {"description": "Not found"}},
)


@retreive_product_router.get("/retreive_product")
async def retreive_product(user_query:str):
    """
    Endpoint to retrieve product information from the vector database based on a user query.

    :param user_query: The query string to search for related banking products.
    :type user_query: str
    :return: A string containing the most relevant product details or an error message.
    :rtype: str
    """
    try:
        print(f"[VECTOR-DB-SERVICE-RETREIVE-PRODUCT] Retrieving documents for query {user_query}...")
        return retrieve_documents(user_query, "sample_bank_products")
    except Exception as e:
        print(f"[VECTOR-DB-SERVICE-RETREIVE-PRODUCT] Error: {str(e)}")
        return f"[VECTOR-DB-SERVICE-RETREIVE-PRODUCT] Error: {str(e)}"

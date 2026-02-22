from fastapi import APIRouter
import os
from backend.vector_db_service.store_products import retrieve_documents

retreive_product_router = APIRouter(
    prefix="/vector_db_service",
    tags=["retreive_product"],
)

import logging

logger = logging.getLogger(__name__)

# Constants
VECTOR_DB_COLLECTION = os.getenv("VECTOR_DB_COLLECTION", "sample_bank_products")

@retreive_product_router.get("/retreive_product")
async def retreive_product(user_query: str):
    """
    Endpoint to retrieve banking product information based on a user's query.
    
    :param user_query: The text query to search for in the vector database.
    :return: The most relevant banking product information found.
    """
    try:
        logger.info(f"Retrieving documents for query {user_query}...")
        # Retrieve relevant documents from the vector database
        result = retrieve_documents(user_query, VECTOR_DB_COLLECTION)
        return result
    except Exception as e:
        logger.error(f"Error in retreive_product: {str(e)}", exc_info=True)
        return f"Error: {str(e)}"

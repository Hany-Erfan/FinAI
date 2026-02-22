from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
import os
import shutil
import logging
from backend.vector_db_service.store_products import (
    read_products_xlsx_and_chunk,
    generate_embeddings,
    store_embeddings,
    get_all_product_ids,
    delete_product,
    delete_all_products,
    upsert_product
)

logger = logging.getLogger(__name__)

# Constants
VECTOR_DB_COLLECTION = os.getenv("VECTOR_DB_COLLECTION", "sample_bank_products")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "backend/vector_db_service/uploads")

manage_documents_router = APIRouter(
    prefix="/vector_db_service",
    tags=["manage_documents"],
)

os.makedirs(UPLOAD_DIR, exist_ok=True)

@manage_documents_router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Uploads an Excel file, parses it into chunks, generates embeddings, 
    and stores them in Qdrant.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
         raise HTTPException(status_code=400, detail="Only Excel files are supported for now.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 1. Parse and chunk
        products_data = read_products_xlsx_and_chunk(file_path)
        
        if not products_data:
            return {"success": False, "message": "No valid product data found in the file."}

        # 2. Extract text for embedding
        texts = [p["text"] for p in products_data]

        # 3. Generate embeddings
        embeddings = generate_embeddings(texts)

        # 4. Prepare for storage
        for i, p in enumerate(products_data):
            p["embedding"] = embeddings[i]

        # 5. Store in Qdrant (default collection)
        store_embeddings(products_data, VECTOR_DB_COLLECTION)

        return {"success": True, "message": f"Successfully processed {len(products_data)} products."}

    except Exception as e:
        logger.error(f"Error processing upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@manage_documents_router.get("/products")
async def list_products():
    """Returns a list of all products (unique questions) currently in the DB."""
    products = get_all_product_ids(VECTOR_DB_COLLECTION)
    return {"success": True, "products": products}

@manage_documents_router.delete("/delete/{product_id}")
async def remove_product(product_id: str):
    """Deletes all chunks associated with a specific product ID."""
    success = delete_product(product_id, VECTOR_DB_COLLECTION)
    if success:
        return {"success": True, "message": f"Deleted product {product_id}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete product")

@manage_documents_router.delete("/clear")
async def clear_all_products():
    """Clears the entire product collection."""
    success = delete_all_products(VECTOR_DB_COLLECTION)
    if success:
        return {"success": True, "message": "Cleared all products from the database"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear products")

@manage_documents_router.post("/upsert")
async def upsert_single_product(product_data: dict):
    """
    Adds or updates a single product item.
    Expects payload: {question_en, answer_en, question_ar, answer_ar, category}
    """
    success = upsert_product(product_data, VECTOR_DB_COLLECTION)
    if success:
        return {"success": True, "message": "Product upserted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to upsert product")

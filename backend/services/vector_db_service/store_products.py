from google import genai
import uuid
import hashlib
from qdrant_client import QdrantClient, models
from google.genai import types
from qdrant_client.models import Distance
import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Constants
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
DEFAULT_COLLECTION = os.getenv("VECTOR_DB_COLLECTION", "sample_bank_products")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it in your .env file.")

qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
google_client = genai.Client(api_key=GOOGLE_API_KEY)



def get_collections():
    """
    Safely retrieves the list of all collections from the Qdrant database.

    :return: A list of collection objects or names, or an empty list if a connection error occurs.
    :rtype: list
    """
    try:
        return qdrant_client.get_collections()
    except Exception as e:
        logger.warning(f"Could not connect to Qdrant: {e}")
        return []

def read_products_xlsx_and_chunk(file_path: str):
    """
    Reads banking product data from a multi-sheet Excel file and converts it into structured text chunks.
    Treats each sheet as a category.
    """
    try:
        xl = pd.ExcelFile(file_path)
    except Exception as e:
        logger.error(f"Error reading Excel file {file_path}: {e}")
        return None

    products_data = []

    for sheet_name in xl.sheet_names:
        category = sheet_name.strip()
        df = xl.parse(sheet_name, header=None)
        
        # 1. Find anchors for English and Arabic sections
        eng_anchors = []
        ara_anchors = []
        max_header_row = -1
        
        # Check first 5 rows for markers (was 2)
        for r_idx in range(min(5, len(df))):
            row = df.iloc[r_idx]
            found_header = False
            for c_idx, val in enumerate(row):
                if pd.isna(val): continue
                val_str = str(val).strip().upper()
                if any(k in val_str for k in ["UXW FINAL COPY", "ENGLISH", "EN_QUESTION", "ENGLISH QUESTION"]):
                    eng_anchors.append(c_idx)
                    found_header = True
                elif any(k in val_str for k in ["ARABIC", "AR_QUESTION", "ARABIC QUESTION", "ARABIC COPY"]):
                    ara_anchors.append(c_idx)
                    found_header = True
            if found_header:
                max_header_row = r_idx
        
        # Unique and sorted
        eng_anchors = sorted(list(set(eng_anchors)))
        ara_anchors = sorted(list(set(ara_anchors)))
        
        # Fallbacks if none found
        if not eng_anchors: 
            eng_anchors = [0]
        if not ara_anchors: 
            ara_anchors = [4] if len(df.columns) > 4 else [min(1, len(df.columns)-1)]

        eng_start = eng_anchors[0]
        ara_start = ara_anchors[0]

        # 2. Iterate rows and extract Q&A
        # Start from the row AFTER the last found header row
        start_row = max_header_row + 1
        
        for r_idx in range(start_row, len(df)):
            row = df.iloc[r_idx]
            
            # Helper to find Q&A pair starting from a column
            def find_qa_pair(start_col):
                # Try start_col, start_col+1, start_col+2 to find a question
                # returns (question, answer) or (None, None)
                for i in range(start_col, min(start_col + 5, len(df.columns) - 1)):
                    q = str(row[i]).strip() if not pd.isna(row[i]) else ""
                    a = str(row[i+1]).strip() if not pd.isna(row[i+1]) else ""
                    
                    if not q or not a: continue

                    # Heuristic for a question: ends with ? or contains specific keywords, and has an answer
                    # Or just long enough strings that look like Q&A
                    is_q = q.endswith('?') or q.endswith('؟') or (len(q) > 15)
                    is_a = len(a) > 5
                    
                    if is_q and is_a:
                        # Ensure we don't pick up headers
                        if q.upper() not in ["ENGLISH", "ARABIC", "UXW FINAL COPY", "QUESTION", "ANSWER", "CATEGORY"]:
                            return q, a
                return None, None

            e_q, e_a = find_qa_pair(eng_start)
            a_q, a_a = find_qa_pair(ara_start)

            if e_q and e_a:
                # Use a deterministic ID based on the English question
                product_id = hashlib.md5(e_q.lower().strip().encode()).hexdigest()
                
                chunk = f"Category: {category}\n\n"
                chunk += f"English Question: {e_q}\n"
                chunk += f"English Answer: {e_a}\n"
                
                payload = {
                    "category": category,
                    "question_en": e_q,
                    "answer_en": e_a,
                }
                
                if a_q and a_a:
                    chunk += f"\nArabic Question: {a_q}\n"
                    chunk += f"Arabic Answer: {a_a}\n"
                    payload.update({
                        "question_ar": a_q,
                        "answer_ar": a_a,
                    })
                
                products_data.append({
                    "id": product_id, 
                    "text": chunk,
                    "payload": payload
                })

    return products_data if products_data else None

def create_collections(collection_name):
    """
    Creates a new collection in the Qdrant database with a fixed vector size of 3072 and Cosine distance.

    :param collection_name: The name of the collection to create.
    :type collection_name: str
    :return: None
    :rtype: None
    """
    qdrant_client.create_collection(collection_name, vectors_config=models.VectorParams(size=3072, distance=Distance.COSINE))

def generate_embeddings(content, task_type='RETRIEVAL_DOCUMENT'):
    """
    Generates vector embeddings for a list of contents using the Gemini embedding model.
    Processes content in batches to avoid timeouts and API limits.

    :param content: A list of text strings to embed.
    :type content: list[str]
    :param task_type: The type of task for the embedding (e.g., 'RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY').
    :type task_type: str
    :return: A list of vector embeddings (lists of floats).
    :rtype: list[list[float]]
    """
    model = "gemini-embedding-001"
    batch_size = 100
    all_embeddings = []

    for i in range(0, len(content), batch_size):
        batch = content[i : i + batch_size]
        response = google_client.models.embed_content(
            model=model,
            contents=batch,
            config=types.EmbedContentConfig(task_type=task_type)
        )
        all_embeddings.extend([e.values for e in response.embeddings])
    
    return all_embeddings

def store_embeddings(product_embeddings_data, collection_name):
    """
    Upserts text-embedding pairs into a specified Qdrant collection.

    :param product_embeddings_data: A list of dicts containing 'id', 'text', 'embedding'.
    :type product_embeddings_data: list[dict]
    :param collection_name: The target Qdrant collection name.
    :type collection_name: str
    :return: None
    :rtype: None
    """
    if not qdrant_client.collection_exists(collection_name):
        create_collections(collection_name)

    all_points = []
    for doc in product_embeddings_data:
        raw_chunk_id = str(doc.get("chunk_id", doc.get("id")))
        product_id = str(doc.get("product_id", doc.get("id")))
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_chunk_id))
        
        # Build comprehensive payload
        payload = {
            "text": doc["text"],
            "product_id": product_id
        }
        # Add any additional fields from doc['payload'] if present
        if "payload" in doc and isinstance(doc["payload"], dict):
            payload.update(doc["payload"])

        all_points.append(
            models.PointStruct(
                id=point_id,
                vector=doc["embedding"],
                payload=payload
            )
        )
    
    # Batch upsert
    batch_size = 100
    for i in range(0, len(all_points), batch_size):
        batch_points = all_points[i : i + batch_size]
        qdrant_client.upsert(collection_name, batch_points)

def upsert_product(product_data: dict, collection_name: str) -> bool:
    """
    Upserts a single product into Qdrant.
    product_data must contain: question_en, answer_en, question_ar, answer_ar, category
    """
    try:
        e_q = product_data.get("question_en", "")
        e_a = product_data.get("answer_en", "")
        a_q = product_data.get("question_ar", "")
        a_a = product_data.get("answer_ar", "")
        category = product_data.get("category", "General")

        if not e_q or not e_a:
            return False

        # Generate the text chunk for RAG
        chunk = f"Category: {category}\n\n"
        chunk += f"English Question: {e_q}\n"
        chunk += f"English Answer: {e_a}\n"
        if a_q and a_a:
            chunk += f"\nArabic Question: {a_q}\n"
            chunk += f"Arabic Answer: {a_a}\n"

        # Generate deterministic point ID
        product_hash = hashlib.md5(e_q.lower().strip().encode()).hexdigest()
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, product_hash))

        # Generate embedding
        embedding = generate_embeddings([chunk], task_type='RETRIEVAL_DOCUMENT')[0]

        # Payload
        payload = {
            "text": chunk,
            "product_id": product_hash,
            "category": category,
            "question_en": e_q,
            "answer_en": e_a,
            "question_ar": a_q,
            "answer_ar": a_a
        }

        if not qdrant_client.collection_exists(collection_name):
            create_collections(collection_name)

        qdrant_client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
            ]
        )
        return True
    except Exception as e:
        logger.error(f"Error upserting product: {e}", exc_info=True)
        return False

def delete_product(product_id: str, collection_name: str):
    logger.info(f"Deleting product {product_id} from {collection_name}")
    try:
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="product_id",
                            match=models.MatchValue(value=str(product_id)),
                        ),
                    ],
                )
            ),
        )
        return True
    except Exception as e:
        logger.error(f"Error deleting product {product_id}: {e}")
        return False

def delete_all_products(collection_name: str) -> bool:
    try:
        if not qdrant_client.collection_exists(collection_name):
            return True
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(), # Empty filter matches everything
            ),
        )
        return True
    except Exception as e:
        logger.error(f"Error deleting all products from {collection_name}: {e}")
        return False

def get_all_product_ids(collection_name: str) -> list[dict]:
    try:
        if not qdrant_client.collection_exists(collection_name):
            return []
            
        records, next_page = qdrant_client.scroll(
            collection_name=collection_name,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )
        products = []
        for record in records:
            p_payload = record.payload
            if p_payload:
                products.append(p_payload)
        return products
    except Exception as e:
        logger.error(f"Error getting products from {collection_name}: {e}")
        return []

def retrieve_documents(query, collection_name, top_k=1):
    """
    Searches a Qdrant collection for the most relevant document based on a text query.

    :param query: The user's search query.
    :type query: str
    :param collection_name: The name of the collection to search in.
    :type collection_name: str
    :param top_k: The number of top results to retrieve (defaults to 1).
    :type top_k: int
    :return: A formatted string containing the retrieved content and its relevance score, or an error message.
    :rtype: str
    """
    logger.info(f"Searching Qdrant: collection={collection_name}, query='{query}'")
    try:
        query_embedding = generate_embeddings([query], task_type='RETRIEVAL_QUERY')
        query_embedding = query_embedding[0]
        
        # Using query_points for search
        results = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_embedding,
            limit=top_k,
            with_payload=True
        )
        
        logger.debug(f"Qdrant raw results: {results}")
        
        # Extract the text and score for the LLM
        extracted_results = []
        if hasattr(results, 'points'):
            for point in results.points:
                text = point.payload.get("text", "No text found")
                score = point.score
                extracted_results.append(f"Score: {score:.4f}\nContent: {text}")
        
        if not extracted_results:
            logger.warning("No documents found in Qdrant.")
            return "No relevant banking product information found for this query."
            
        final_output = "\n\n---\n\n".join(extracted_results)
        logger.info(f"Returning {len(extracted_results)} results to Agent")
        return final_output
        
    except Exception as e:
        logger.error(f"Error in retrieve_documents: {str(e)}", exc_info=True)
        return f"Error searching product database: {str(e)}"

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # create_collections("sample_bank_products")
    print(get_collections())
    
    query = "what is the payout frequency of 3 year certificate?"
    results = retrieve_documents(query, "sample_bank_products")
    print(results)

    
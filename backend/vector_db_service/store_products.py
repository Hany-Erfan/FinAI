from google import genai
from qdrant_client import QdrantClient, models
from google.genai import types
from qdrant_client.models import Distance
import os
import pandas as pd

QDRANT_URL = os.getenv("QDRANT_URL", "https://2580c3f4-7869-40a8-b26b-3087029a69b1.europe-west3-0.gcp.cloud.qdrant.io:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY","***REMOVED***")

qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
google_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY","***REMOVED***")) 


def get_collections():
    """
    Safely retrieves the list of all collections from the Qdrant database.

    :return: A list of collection objects or names, or an empty list if a connection error occurs.
    :rtype: list
    """
    try:
        return qdrant_client.get_collections()
    except Exception as e:
        print(f"Warning: Could not connect to Qdrant: {e}")
        return []

def read_products_xlsx_and_chunk(file_path: str):
    """
    Reads banking product data from an Excel file and converts it into structured text chunks.

    :param file_path: The absolute or relative path to the Excel (.xlsx) file.
    :type file_path: str
    :return: A list of formatted text strings, one for each product found in the file, or None if reading fails.
    :rtype: list[str] | None
    """
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None

    products_text = []

    # Iterate over product columns (English, Arabic pairs) starting from column C (index 2)
    # We step by 2: (Eng_Col, Ar_Col), (Eng_Col, Ar_Col)...
    for i in range(2, len(df.columns), 2):
        if i + 1 >= len(df.columns):
            break

        # Check if we have a valid product ID at row 0
        product_id = df.iloc[0, i]
        if pd.isna(product_id):
            continue

        chunk = f"Product ID: {product_id}\n\n"

        # --- English Section ---
        chunk += "English:\n"
        early_break_lines = []

        # Start from row 1 (since row 0 is Product ID)
        for idx in range(1, len(df)):
            field_name = df.iloc[idx, 0] # Column A: Field (English)
            value = df.iloc[idx, i]      # Column i: Product Value (English)

            if pd.isna(value) or pd.isna(field_name):
                continue
            
            field_name = str(field_name).strip()
            value = str(value).strip()

            if "Early Break Penalty" in field_name:
                # Format: "Early Break Penalty (6-12 months)" -> "6-12 months"
                duration = field_name.replace("Early Break Penalty", "").strip(" ()")
                early_break_lines.append(f"- {duration}: {value}")
            else:
                chunk += f"{field_name}: {value}\n"
        
        # Append grouped Early Break Penalty lines if any
        if early_break_lines:
            chunk += "Early Break Penalty:\n"
            chunk += "\n".join(early_break_lines) + "\n"

        # --- Arabic Section ---
        chunk += "\nArabic:\n"
        for idx in range(1, len(df)):
            field_name = df.iloc[idx, 1] # Column B: Field (Arabic)
            value = df.iloc[idx, i+1]    # Column i+1: Product Value (Arabic)

            if pd.isna(value) or pd.isna(field_name):
                continue

            field_name = str(field_name).strip()
            value = str(value).strip()
            
            chunk += f"{field_name}: {value}\n"

        products_text.append(chunk)

    return products_text

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

    :param content: A list of text strings to embed.
    :type content: list[str]
    :param task_type: The type of task for the embedding (e.g., 'RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY').
    :type task_type: str
    :return: A list of vector embeddings (lists of floats).
    :rtype: list[list[float]]
    """
    model = "gemini-embedding-001"
    response = google_client.models.embed_content(
        model=model,
        contents=content,
        config=types.EmbedContentConfig(task_type=task_type)
    )
    
    return [e.values for e in response.embeddings]

def store_embeddings(text_embeddings_pairs, collection_name):
    """
    Upserts text-embedding pairs into a specified Qdrant collection.

    :param text_embeddings_pairs: A list of tuples, each containing (text_content, vector_embedding).
    :type text_embeddings_pairs: list[tuple[str, list[float]]]
    :param collection_name: The target Qdrant collection name.
    :type collection_name: str
    :return: None
    :rtype: None
    """
    points = []
    for i, doc in enumerate(text_embeddings_pairs):
        points.append(
            models.PointStruct(
                id=i,
                vector=doc[1],
                payload={"text": doc[0]}
            )
        )
    qdrant_client.upsert(collection_name, points)

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
    print(f"[VECTOR-DB-SERVICE] Searching Qdrant: collection={collection_name}, query='{query}'")
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
        
        print(f"[VECTOR-DB-SERVICE] Qdrant raw results: {results}")
        
        # Extract the text and score for the LLM
        extracted_results = []
        if hasattr(results, 'points'):
            for point in results.points:
                text = point.payload.get("text", "No text found")
                score = point.score
                extracted_results.append(f"Score: {score:.4f}\nContent: {text}")
        
        if not extracted_results:
            print("[VECTOR-DB-SERVICE] Warning: No documents found in Qdrant.")
            return "No relevant banking product information found for this query."
            
        final_output = "\n\n---\n\n".join(extracted_results)
        print(f"[VECTOR-DB-SERVICE] Returning to Agent: {final_output[:200]}...")
        return final_output
        
    except Exception as e:
        print(f"[VECTOR-DB-SERVICE] Error in retrieve_documents: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error searching product database: {str(e)}"

if __name__ == "__main__":
    # Get the directory of the current file to locate the Excel file reliably
    current_dir = os.path.dirname(os.path.abspath(__file__))
    xlsx_file = os.path.join(current_dir, "Bilingual_Certificate_Products.xlsx")
    
    if os.path.exists(xlsx_file):
        print(f"Reading file: {xlsx_file}")
        products = read_products_xlsx_and_chunk(xlsx_file)
        if products:
            print(f"\nFound {len(products)} products.")
        else:
             print("No products found or error reading file.")
    else:
        print(f"File not found: {xlsx_file}")

    # Create collections
    print("Creating collections...")
    # create_collections("sample_bank_products")
    print("Collections created successfully")
    print(get_collections())

    print("\nGenerating embeddings...")
    # products_embeddings = generate_embeddings(products, task_type='RETRIEVAL_DOCUMENT')
    print("Embeddings generated successfully")

    #creating text-embedding pairs
    # text_embeddings_pairs = list(zip(products, products_embeddings))
    print("\nStoring embeddings...")
    # store_embeddings(text_embeddings_pairs, "sample_bank_products")
    print("Embeddings stored successfully")

    query = "what is the payout frequency of 3 year certificate?"

    print("\nRetrieving documents...")
    results = retrieve_documents(query, "sample_bank_products")
    print(results)

    print("\nDocuments retrieved successfully")

    
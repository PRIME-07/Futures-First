import chromadb
from sentence_transformers import SentenceTransformer
import asyncio
import uuid
from app.core.database import get_mongo_db
from app.core.config import settings

# Initialize ChromaDB client
chroma_client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)

# Collection name we'll use for all documents
COLLECTION_NAME = "document_chunks"

# Load model globally to avoid reloading. 
model = SentenceTransformer("all-MiniLM-L6-v2")

def get_or_create_collection():
    return chroma_client.get_or_create_collection(name=COLLECTION_NAME)

async def build_index_for_session(session_id: str):
    """
    Fetches all PDF texts for a session from MongoDB, chunks them, and stores them in ChromaDB.
    """
    mongo_db = get_mongo_db()
    cursor = mongo_db.pdf_registry.find({"session_id": session_id})
    pdfs = await cursor.to_list(length=None)
    
    if not pdfs:
        return {"status": "No PDFs found for this session"}
        
    def _process():
        chunks = []
        chunk_size = 100
        overlap = 30
        
        for pdf in pdfs:
            filename = pdf.get("filename", "unknown")
            pages = pdf.get("pages", [])
            
            if pages:
                # If page-by-page data is available, chunk per-page
                for p in pages:
                    p_num = p.get("page_num", 1)
                    text = p.get("text", "")
                    
                    words = text.split()
                    for i in range(0, len(words), chunk_size - overlap):
                        chunk_words = words[i:i + chunk_size]
                        chunk_text = " ".join(chunk_words)
                        if chunk_text.strip():
                            chunks.append({
                                "text": chunk_text, 
                                "filename": filename,
                                "page_num": p_num
                            })
            else:
                # Fallback for legacy database records
                text = pdf.get("raw_text", "")
                words = text.split()
                for i in range(0, len(words), chunk_size - overlap):
                    chunk_words = words[i:i + chunk_size]
                    chunk_text = " ".join(chunk_words)
                    if chunk_text.strip():
                        chunks.append({
                            "text": chunk_text, 
                            "filename": filename,
                            "page_num": 1
                        })
                    
        if not chunks:
            return None
            
        texts = [c["text"] for c in chunks]
        embeddings = model.encode(texts).tolist() # ChromaDB expects a list of float lists
        
        ids = [f"{session_id}_{uuid.uuid4().hex}" for _ in range(len(chunks))]
        
        metadatas = [{
            "session_id": session_id,
            "filename": c["filename"],
            "page_num": c["page_num"]
        } for c in chunks]
        
        collection = get_or_create_collection()
        
        # Clean up any existing chunks for this session first to avoid duplicates
        collection.delete(where={"session_id": session_id})
        
        # Add to ChromaDB
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
        return len(chunks)

    result = await asyncio.to_thread(_process)
    if result is not None:
        return {"status": "success", "chunks_indexed": result}
    else:
        return {"status": "failed", "reason": "Could not create chunks"}

async def retrieve_context(session_id: str, query: str, top_k: int = 3):
    """
    Retrieve relevant chunks for a given query in a session from ChromaDB.
    """
    collection = get_or_create_collection()
    
    count_res = collection.get(where={"session_id": session_id}, limit=1)
    if not count_res or not count_res["ids"]:
        await build_index_for_session(session_id)
        
    def _search():
        query_vector = model.encode([query]).tolist()[0]
        
        # Query ChromaDB collection with session filter
        search_res = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where={"session_id": session_id}
        )
        
        results = []
        if search_res and search_res["ids"] and search_res["ids"][0]:
            ids = search_res["ids"][0]
            distances = search_res["distances"][0] if search_res["distances"] else [0.0] * len(ids)
            documents = search_res["documents"][0]
            metadatas = search_res["metadatas"][0]
            
            for i in range(len(ids)):
                meta = metadatas[i]
                results.append({
                    "text": documents[i],
                    "filename": meta.get("filename", "unknown"),
                    "page_num": meta.get("page_num", 1),
                    "distance": float(distances[i])
                })
        return results
        
    return await asyncio.to_thread(_search)

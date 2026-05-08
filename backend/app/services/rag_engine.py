import faiss
from sentence_transformers import SentenceTransformer
import asyncio
from app.core.database import get_mongo_db

# Transient, in-memory FAISS indices mapped by session_id
# Format: { "session_id": { "index": faiss_index, "chunks": [{"text": str, "filename": str, "page_num": int}] } }
_SESSION_INDICES = {}

# Load model globally to avoid reloading. 
model = SentenceTransformer("all-MiniLM-L6-v2")

async def build_index_for_session(session_id: str):
    """
    Fetches all PDF texts for a session from MongoDB, chunks them, and builds the FAISS index.
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
        embeddings = model.encode(texts)
        
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)
        
        return index, chunks

    result = await asyncio.to_thread(_process)
    if result:
        index, chunks = result
        _SESSION_INDICES[session_id] = {
            "index": index,
            "chunks": chunks
        }
        return {"status": "success", "chunks_indexed": len(chunks)}
    else:
        return {"status": "failed", "reason": "Could not create chunks"}

async def retrieve_context(session_id: str, query: str, top_k: int = 3):
    """
    Retrieve relevant chunks for a given query in a session.
    """
    if session_id not in _SESSION_INDICES:
        await build_index_for_session(session_id)
        
    if session_id not in _SESSION_INDICES:
        return []
        
    session_data = _SESSION_INDICES[session_id]
    index = session_data["index"]
    chunks = session_data["chunks"]
    
    def _search():
        query_vector = model.encode([query])
        distances, indices = index.search(query_vector, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(chunks):
                results.append({
                    "text": chunks[idx]["text"],
                    "filename": chunks[idx]["filename"],
                    "page_num": chunks[idx].get("page_num", 1),
                    "distance": float(distances[0][i])
                })
        return results
        
    return await asyncio.to_thread(_search)

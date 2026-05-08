from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import rag_engine

router = APIRouter(prefix="/rag", tags=["rag"])

class RetrieveRequest(BaseModel):
    session_id: str
    query: str
    top_k: int = 3

@router.post("/build_index/{session_id}")
async def build_index(session_id: str):
    try:
        res = await rag_engine.build_index_for_session(session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    try:
        res = await rag_engine.retrieve_context(req.session_id, req.query, req.top_k)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

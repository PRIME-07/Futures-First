from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.ingestion import process_csv_ingestion, process_pdf_ingestion

router = APIRouter(prefix="/ingest", tags=["ingestion"])

class ExternalDBRequest(BaseModel):
    session_id: str
    db_type: str  # "postgresql", "mysql", or "sqlite"
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None

@router.post("/")
async def ingest_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    dataset_name: Optional[str] = Form(None)
):
    try:
        content = await file.read()
        resolved_dataset_name = dataset_name or file.filename
        filename_lower = file.filename.lower()
        
        if filename_lower.endswith(('.csv', '.xls', '.xlsx')):
            result = await process_csv_ingestion(
                file_content=content,
                filename=file.filename,
                dataset_name=resolved_dataset_name,
                session_id=session_id
            )
            
            # Clean up ObjectId for JSON response
            result["_id"] = str(result["_id"])
            return {"status": "success", "data": result}
            
        elif filename_lower.endswith('.pdf'):
            result = await process_pdf_ingestion(
                file_content=content,
                filename=file.filename,
                session_id=session_id
            )
            
            if "_id" in result:
                result["_id"] = str(result["_id"])
            return {"status": "success", "data": result}
            
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format for '{file.filename}'. Supported formats: .csv, .xls, .xlsx, .pdf (case-insensitive)."
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        from app.services.ingestion import delete_session_data
        result = await delete_session_data(session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}/files/{filename}")
async def delete_file(session_id: str, filename: str):
    try:
        from app.services.ingestion import delete_file_from_session
        result = await delete_file_from_session(session_id, filename)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# External SQL Database Connection Endpoints

@router.post("/connect_db")
async def connect_external_db(req: ExternalDBRequest):
    """Connect an external SQL database, introspect its schema, and register tables."""
    try:
        from app.services.external_db import add_external_connection
        result = await add_external_connection(
            session_id=req.session_id,
            db_type=req.db_type,
            host=req.host,
            port=req.port,
            username=req.username,
            password=req.password,
            database_name=req.database_name,
        )
        return {"status": "success", "data": result}
    except (ValueError, ConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

@router.delete("/sessions/{session_id}/connections/{connection_id}")
async def remove_external_connection(session_id: str, connection_id: str):
    """Remove an external SQL connection and its associated datasets from a session."""
    try:
        from app.services.external_db import remove_external_connection as _remove
        result = await _remove(session_id, connection_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/connections")
async def list_connections(session_id: str):
    """List all external SQL database connections for a session."""
    try:
        from app.services.external_db import list_session_connections
        connections = await list_session_connections(session_id)
        return {"status": "success", "data": connections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_active_sessions():
    """List all unique active sessions with dataset, PDF, and database connection summaries."""
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()
        
        sessions = {}
        
        # 1. Gather from dataset registry
        cursor = db.dataset_registry.aggregate([
            {"$group": {"_id": "$session_id", "count": {"$sum": 1}}}
        ])
        async for doc in cursor:
            sid = doc["_id"]
            if sid:
                sessions[sid] = {
                    "session_id": sid,
                    "dataset_count": doc["count"],
                    "pdf_count": 0,
                    "connection_count": 0
                }
                
        # 2. Gather from PDF registry
        cursor = db.pdf_registry.aggregate([
            {"$group": {"_id": "$session_id", "count": {"$sum": 1}}}
        ])
        async for doc in cursor:
            sid = doc["_id"]
            if sid:
                if sid not in sessions:
                    sessions[sid] = {
                        "session_id": sid,
                        "dataset_count": 0,
                        "pdf_count": doc["count"],
                        "connection_count": 0
                    }
                else:
                    sessions[sid]["pdf_count"] = doc["count"]
                    
        # 3. Gather from SQL connections
        cursor = db.sql_connections.aggregate([
            {"$group": {"_id": "$session_id", "count": {"$sum": 1}}}
        ])
        async for doc in cursor:
            sid = doc["_id"]
            if sid:
                if sid not in sessions:
                    sessions[sid] = {
                        "session_id": sid,
                        "dataset_count": 0,
                        "pdf_count": 0,
                        "connection_count": doc["count"]
                    }
                else:
                    sessions[sid]["connection_count"] = doc["count"]
                    
        # 4. Gather from chats
        cursor = db.chats.aggregate([
            {"$group": {"_id": "$session_id", "count": {"$sum": 1}}}
        ])
        async for doc in cursor:
            sid = doc["_id"]
            if sid:
                if sid not in sessions:
                    sessions[sid] = {
                        "session_id": sid,
                        "dataset_count": 0,
                        "pdf_count": 0,
                        "connection_count": 0
                    }
                    
        return {"status": "success", "data": list(sessions.values())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.get("/sessions/{session_id}/sources")
async def list_session_sources(session_id: str):
    """List all connected sources (CSV/Excel files, PDFs, SQL connections) for a specific session."""
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()
        
        # 1. Datasets
        datasets = []
        cursor = db.dataset_registry.find({"session_id": session_id})
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if "created_at" in doc and doc["created_at"]:
                doc["created_at"] = doc["created_at"].isoformat()
            datasets.append(doc)
            
        # 2. PDFs
        pdfs = []
        cursor = db.pdf_registry.find({"session_id": session_id})
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if "created_at" in doc and doc["created_at"]:
                doc["created_at"] = doc["created_at"].isoformat()
            # Omit massive blocks to keep response lightweight
            doc.pop("raw_text", None)
            doc.pop("pages", None)
            pdfs.append(doc)
            
        # 3. SQL Connections
        connections = []
        cursor = db.sql_connections.find({"session_id": session_id})
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if "created_at" in doc and doc["created_at"]:
                doc["created_at"] = doc["created_at"].isoformat()
            connections.append(doc)
            
        return {
            "status": "success",
            "session_id": session_id,
            "data": {
                "datasets": datasets,
                "pdfs": pdfs,
                "sql_connections": connections
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list session sources: {str(e)}")



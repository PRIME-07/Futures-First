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
    dataset_name: str = Form(...),
    session_id: str = Form(...)
):
    try:
        content = await file.read()
        
        if file.filename.endswith(('.csv', '.xls', '.xlsx')):
            result = await process_csv_ingestion(
                file_content=content,
                filename=file.filename,
                dataset_name=dataset_name,
                session_id=session_id
            )
            
            # Clean up ObjectId for JSON response
            result["_id"] = str(result["_id"])
            return {"status": "success", "data": result}
            
        elif file.filename.endswith('.pdf'):
            result = await process_pdf_ingestion(
                file_content=content,
                filename=file.filename,
                session_id=session_id
            )
            
            if "_id" in result:
                result["_id"] = str(result["_id"])
            return {"status": "success", "data": result}
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
            
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


# ---------------------------------------------------------------------------
# External SQL Database Connection Endpoints
# ---------------------------------------------------------------------------

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



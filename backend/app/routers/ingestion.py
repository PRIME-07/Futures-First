from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.ingestion import process_csv_ingestion, process_pdf_ingestion

router = APIRouter(prefix="/ingest", tags=["ingestion"])

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

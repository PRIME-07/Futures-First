import io
import re
import uuid
import pandas as pd
from datetime import datetime
import asyncio
from app.core.database import engine, get_mongo_db

def sanitize_column_name(col: str) -> str:
    """Clean column headers to lowercase, snake_case, and strip special characters."""
    col = str(col).lower()
    col = re.sub(r'[^a-z0-9_]', '_', col)
    col = re.sub(r'_+', '_', col).strip('_')
    return col

def infer_semantic_mappings(df: pd.DataFrame) -> dict:
    """Infer semantic mapping from dataframe column types."""
    semantics = {}
    for col in df.columns:
        dtype = str(df[col].dtype)
        if 'datetime' in dtype:
            semantics[col] = {"role": "temporal", "type": "datetime"}
        elif 'int' in dtype or 'float' in dtype:
            semantics[col] = {"role": "metric", "type": "numeric"}
        else:
            semantics[col] = {"role": "dimension", "type": "categorical"}
    return semantics

def detect_capabilities(semantics: dict) -> dict:
    """Detect table capabilities based on semantics."""
    has_numeric = any(s["role"] == "metric" for s in semantics.values())
    has_temporal = any(s["role"] == "temporal" for s in semantics.values())
    has_categorical = any(s["role"] == "dimension" for s in semantics.values())
    
    return {
        "supports_trends": has_numeric and has_temporal,
        "supports_grouping": has_numeric and has_categorical,
        "supports_correlation": sum(1 for s in semantics.values() if s["role"] == "metric") >= 2
    }

async def process_csv_ingestion(file_content: bytes, filename: str, dataset_name: str, session_id: str):
    """
    Process uploaded CSV/XLSX.
    Uses asyncio.to_thread to run Pandas and SQLAlchemy synchronously without blocking.
    """
    def _process_sync():
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_content))
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            raise ValueError("Unsupported file format")

        # Clean headers
        df.columns = [sanitize_column_name(col) for col in df.columns]

        # Drop rows with any missing values to ensure statistical clean-ness
        df.dropna(inplace=True)

        # Generate explicit dataset_uuid and Postgres table name
        dataset_uuid = str(uuid.uuid4())
        postgres_table_name = f"dataset_{dataset_uuid.replace('-', '_')}"

        # Write to Postgres dynamically
        df.to_sql(name=postgres_table_name, con=engine, if_exists='replace', index=False)

        # Semantics & Capabilities
        semantics = infer_semantic_mappings(df)
        capabilities = detect_capabilities(semantics)
        
        return df, dataset_uuid, postgres_table_name, semantics, capabilities

    # Run blocking operations in thread
    df, dataset_uuid, postgres_table_name, semantics, capabilities = await asyncio.to_thread(_process_sync)

    # Register in MongoDB DatasetRegistry
    mongo_db = get_mongo_db()
    registry_entry = {
        "dataset_uuid": dataset_uuid,
        "session_id": session_id,
        "dataset_name": dataset_name,
        "original_filename": filename,
        "postgres_table_name": postgres_table_name,
        "row_count": len(df),
        "columns": list(df.columns),
        "semantic_mapping": semantics,
        "capabilities": capabilities,
        "created_at": datetime.utcnow()
    }
    
    await mongo_db.dataset_registry.insert_one(registry_entry)

    return registry_entry

async def process_pdf_ingestion(file_content: bytes, filename: str, session_id: str):
    """
    Extract text from PDF page by page.
    """
    import pdfplumber
    
    def _extract_sync():
        pages = []
        full_text = ""
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for idx, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                pages.append({
                    "page_num": idx + 1,
                    "text": page_text
                })
                full_text += page_text + "\n"
        return pages, full_text

    # Run blocking operations in thread
    pages, full_text = await asyncio.to_thread(_extract_sync)
    
    mongo_db = get_mongo_db()
    
    pdf_entry = {
        "session_id": session_id,
        "filename": filename,
        "content_length": len(full_text),
        "raw_text": full_text,
        "pages": pages,
        "created_at": datetime.utcnow()
    }
    
    await mongo_db.pdf_registry.insert_one(pdf_entry)
    
    return {"filename": filename, "content_length": len(full_text), "status": "Text extracted"}


async def delete_file_from_session(session_id: str, filename: str):
    """
    Remove an uploaded file (CSV or PDF) from a session.
    If CSV, drops its associated Postgres table and deletes its MongoDB registry entry.
    If PDF, deletes its MongoDB registry entry.
    """
    mongo_db = get_mongo_db()
    
    # Check if CSV
    csv_doc = await mongo_db.dataset_registry.find_one({"session_id": session_id, "original_filename": filename})
    if csv_doc:
        table_name = csv_doc.get("postgres_table_name")
        if table_name:
            def _drop():
                with engine.connect() as conn:
                    # Drop table safely
                    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            try:
                await asyncio.to_thread(_drop)
            except Exception as e:
                # Log and continue even if drop table fails
                print(f"Failed to drop table {table_name}: {e}")
        
        await mongo_db.dataset_registry.delete_one({"_id": csv_doc["_id"]})
        return {"status": "success", "message": f"Successfully removed CSV dataset '{filename}' from session"}

    # Check if PDF
    pdf_doc = await mongo_db.pdf_registry.find_one({"session_id": session_id, "filename": filename})
    if pdf_doc:
        await mongo_db.pdf_registry.delete_one({"_id": pdf_doc["_id"]})
        return {"status": "success", "message": f"Successfully removed PDF '{filename}' from session"}

    raise ValueError(f"File '{filename}' not found in session '{session_id}'")


async def delete_session_data(session_id: str):
    """
    Wipes all session-specific data.
    Drops any associated Postgres tables (uploaded files only), deletes all file registry records,
    external connection metadata, and removes all charts.
    """
    mongo_db = get_mongo_db()
    
    # 1. Fetch and drop only uploaded CSV tables (not external DB tables)
    cursor = mongo_db.dataset_registry.find({"session_id": session_id})
    datasets = await cursor.to_list(length=100)
    for ds in datasets:
        # Only drop tables that were created locally from uploaded files
        if ds.get("source_type") != "database":
            table_name = ds.get("postgres_table_name")
            if table_name:
                def _drop():
                    with engine.connect() as conn:
                        conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                try:
                    await asyncio.to_thread(_drop)
                except Exception as e:
                    print(f"Failed to drop table {table_name} during session wipe: {e}")
                
    # 2. Clear MongoDB datasets, PDFs, charts, and external connections
    await mongo_db.dataset_registry.delete_many({"session_id": session_id})
    await mongo_db.pdf_registry.delete_many({"session_id": session_id})
    await mongo_db.charts.delete_many({"session_id": session_id})
    await mongo_db.sql_connections.delete_many({"session_id": session_id})
    
    return {"status": "success", "message": f"Wiped all datasets, PDFs, charts, and connections for session '{session_id}'"}


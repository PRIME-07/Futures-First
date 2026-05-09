"""
External SQL Database Connection Service.

Handles session-scoped connectivity to external SQL databases (PostgreSQL, MySQL, SQLite).
Provides connection validation, schema introspection, unified dataset registration,
and session-scoped lifecycle management.

All access is strictly read-only and analytical.
"""
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy import inspect, text

from app.core.database import create_external_engine, get_mongo_db
from app.services.ingestion import infer_semantic_mappings, detect_capabilities

logger = logging.getLogger(__name__)


# Schema Introspection

def _introspect_tables(engine) -> List[Dict[str, Any]]:
    """
    Use SQLAlchemy's inspection API to extract table names, column names, and types.
    Returns a clean, serializable list of table metadata.
    """
    inspector = inspect(engine)
    tables = []

    for table_name in inspector.get_table_names():
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
            })
        tables.append({
            "table_name": table_name,
            "columns": columns,
        })

    return tables


def _build_semantic_mapping_from_introspection(columns: List[Dict]) -> Dict:
    """
    Build a semantic mapping from SQLAlchemy introspected column types.
    Maps SQL types to our analytical roles (metric, dimension, temporal).
    """
    semantics = {}
    for col in columns:
        col_type = col["type"].upper()
        col_name = col["name"]

        if any(t in col_type for t in ("INT", "FLOAT", "NUMERIC", "DECIMAL", "DOUBLE", "REAL")):
            semantics[col_name] = {"role": "metric", "type": "numeric"}
        elif any(t in col_type for t in ("DATE", "TIME", "TIMESTAMP")):
            semantics[col_name] = {"role": "temporal", "type": "datetime"}
        else:
            semantics[col_name] = {"role": "dimension", "type": "categorical"}

    return semantics


# Connection Management

async def add_external_connection(
    session_id: str,
    db_type: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    database_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate an external SQL database connection, introspect its schema,
    register each table as a unified dataset, and persist connection metadata.

    Steps:
    1. Create an ephemeral SQLAlchemy engine.
    2. Validate connectivity with a lightweight test query.
    3. Introspect all tables and columns.
    4. Register each table in MongoDB dataset_registry with source_type="database".
    5. Save connection metadata in MongoDB sql_connections collection.
    6. Dispose the engine (ephemeral lifecycle).
    """
    # 1. Create ephemeral engine
    try:
        ext_engine = create_external_engine(
            db_type=db_type, host=host, port=port,
            username=username, password=password, database_name=database_name
        )
    except Exception as e:
        raise ValueError(f"Failed to build connection URL: {e}")

    # 2. Validate connectivity
    def _validate():
        with ext_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    try:
        await asyncio.to_thread(_validate)
    except Exception as e:
        ext_engine.dispose()
        raise ConnectionError(f"Connection validation failed: {e}")

    # 3. Introspect schema
    try:
        tables = await asyncio.to_thread(_introspect_tables, ext_engine)
    except Exception as e:
        ext_engine.dispose()
        raise ValueError(f"Schema introspection failed: {e}")

    if not tables:
        ext_engine.dispose()
        raise ValueError("Connected successfully but no tables found in the database.")

    # 4. Generate connection ID
    connection_id = str(uuid.uuid4())

    # 5. Register each table as a unified dataset in dataset_registry
    mongo_db = get_mongo_db()
    registered_datasets = []

    for table_info in tables:
        table_name = table_info["table_name"]
        columns = table_info["columns"]

        semantics = _build_semantic_mapping_from_introspection(columns)
        capabilities = detect_capabilities(semantics)

        dataset_uuid = str(uuid.uuid4())

        registry_entry = {
            "dataset_uuid": dataset_uuid,
            "session_id": session_id,
            "dataset_name": table_name,
            "original_filename": f"{database_name}.{table_name}",
            # Source routing fields
            "source_type": "database",
            "connection_id": connection_id,
            "external_table_name": table_name,
            "external_db_type": db_type,
            "external_host": host,
            "external_port": port,
            "external_username": username,
            "external_password": password,
            "external_database_name": database_name,
            # Schema metadata
            "columns": [c["name"] for c in columns],
            "semantic_mapping": semantics,
            "capabilities": capabilities,
            "created_at": datetime.now(),
        }

        await mongo_db.dataset_registry.insert_one(registry_entry)
        registered_datasets.append({
            "dataset_uuid": dataset_uuid,
            "table_name": table_name,
            "columns": [c["name"] for c in columns],
        })

    # 6. Persist connection metadata (without engine objects)
    connection_doc = {
        "connection_id": connection_id,
        "session_id": session_id,
        "db_type": db_type,
        "host": host,
        "port": port,
        "database_name": database_name,
        "tables": tables,
        "dataset_count": len(registered_datasets),
        "created_at": datetime.now(),
    }

    await mongo_db.sql_connections.insert_one(connection_doc)

    # 7. Dispose ephemeral engine
    ext_engine.dispose()
    logger.info(f"External DB connected: {db_type}://{host}/{database_name} — {len(tables)} tables registered for session {session_id}")

    return {
        "connection_id": connection_id,
        "db_type": db_type,
        "database_name": database_name,
        "tables_registered": len(registered_datasets),
        "datasets": registered_datasets,
    }


async def remove_external_connection(session_id: str, connection_id: str) -> Dict[str, Any]:
    """
    Remove an external SQL connection and all its associated dataset registrations.
    Session-scoped: only removes the connection matching both session_id AND connection_id.
    """
    mongo_db = get_mongo_db()

    # Verify connection exists for this session
    conn_doc = await mongo_db.sql_connections.find_one({
        "session_id": session_id,
        "connection_id": connection_id
    })

    if not conn_doc:
        raise ValueError(f"Connection '{connection_id}' not found in session '{session_id}'")

    # Remove all dataset_registry entries tied to this connection
    delete_result = await mongo_db.dataset_registry.delete_many({
        "session_id": session_id,
        "connection_id": connection_id,
    })

    # Remove the connection metadata itself
    await mongo_db.sql_connections.delete_one({"_id": conn_doc["_id"]})

    logger.info(f"Removed external connection {connection_id}: {delete_result.deleted_count} datasets unregistered")

    return {
        "status": "success",
        "message": f"Removed connection '{connection_id}' and {delete_result.deleted_count} associated datasets",
    }


async def list_session_connections(session_id: str) -> List[Dict[str, Any]]:
    """
    List all external SQL database connections for a session.
    Returns connection metadata including introspected table schemas.
    """
    mongo_db = get_mongo_db()
    cursor = mongo_db.sql_connections.find({"session_id": session_id})
    connections = await cursor.to_list(length=50)

    # Clean MongoDB ObjectId for JSON serialization
    for conn in connections:
        conn["_id"] = str(conn["_id"])

    return connections

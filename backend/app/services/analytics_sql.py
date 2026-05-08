import asyncio
import decimal
from sqlalchemy import text
from app.core.database import engine, get_mongo_db

def sanitize_rows(rows: list) -> list:
    sanitized = []
    for r in rows:
        new_row = {}
        for k, v in r.items():
            if isinstance(v, decimal.Decimal):
                new_row[k] = float(v)
            else:
                new_row[k] = v
        sanitized.append(new_row)
    return sanitized

async def get_dataset_entry(dataset_uuid: str) -> dict:
    mongo_db = get_mongo_db()
    entry = await mongo_db.dataset_registry.find_one({"dataset_uuid": dataset_uuid})
    if not entry:
        raise ValueError(f"Dataset with UUID {dataset_uuid} not found.")
    return entry

async def resolve_table_name(dataset_uuid: str) -> str:
    entry = await get_dataset_entry(dataset_uuid)
    return entry["postgres_table_name"]

async def run_aggregation(dataset_uuid: str, metric: str, group_by: str, filter_dict: dict = None):
    entry = await get_dataset_entry(dataset_uuid)
    table_name = entry["postgres_table_name"]
    valid_cols = entry.get("columns", [])
    
    # Strictly validate against schema columns
    if metric not in valid_cols:
        raise ValueError(f"Metric column '{metric}' does not exist in dataset. Valid columns are: {valid_cols}")
    if group_by not in valid_cols:
        raise ValueError(f"Group by column '{group_by}' does not exist in dataset. Valid columns are: {valid_cols}")
        
    if filter_dict:
        for k in filter_dict.keys():
            if k not in valid_cols:
                raise ValueError(f"Filter column '{k}' does not exist in dataset. Valid columns are: {valid_cols}")

    def _execute():
        where_clauses = []
        bind_params = {}
        
        if filter_dict:
            for k, v in filter_dict.items():
                where_clauses.append(f"{k} = :{k}")
                bind_params[k] = v
                
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
            
        query_str = f"SELECT {group_by}, SUM({metric}) as total_{metric} FROM {table_name} {where_sql} GROUP BY {group_by} ORDER BY total_{metric} DESC"
        
        with engine.connect() as conn:
            result = conn.execute(text(query_str), bind_params)
            return sanitize_rows([dict(row._mapping) for row in result])

    return await asyncio.to_thread(_execute)

async def run_join_aggregation(left_uuid: str, right_uuid: str, join_key: str, metric: str, group_by: str):
    try:
        left_entry = await get_dataset_entry(left_uuid)
        right_entry = await get_dataset_entry(right_uuid)
        
        left_table = left_entry["postgres_table_name"]
        right_table = right_entry["postgres_table_name"]
        
        left_cols = left_entry.get("columns", [])
        right_cols = right_entry.get("columns", [])
        
        if not join_key or join_key not in left_cols or join_key not in right_cols:
            # Intelligently auto-resolve matching join columns
            common_cols = [c for c in left_cols if c in right_cols]
            if common_cols:
                id_cols = [c for c in common_cols if "id" in c]
                join_key = id_cols[0] if id_cols else common_cols[0]
            else:
                raise ValueError("cant join as no matching columns are found")

        # Determine where group_by and metric reside
        l_group = group_by in left_cols
        r_group = group_by in right_cols
        if not l_group and not r_group:
            raise ValueError(f"Group by column '{group_by}' does not exist in either dataset. Left columns: {left_cols}, Right columns: {right_cols}")

        l_metric = metric in left_cols
        r_metric = metric in right_cols
        if not l_metric and not r_metric:
            raise ValueError(f"Metric column '{metric}' does not exist in either dataset. Left columns: {left_cols}, Right columns: {right_cols}")

        group_by_col = f"l.{group_by}" if l_group else f"r.{group_by}"
        metric_col = f"r.{metric}" if r_metric else f"l.{metric}"

        def _execute():
            query_str = f"""
                SELECT {group_by_col} as {group_by}, SUM({metric_col}) as total_{metric}
                FROM {left_table} l
                JOIN {right_table} r ON l.{join_key} = r.{join_key}
                GROUP BY {group_by_col}
                ORDER BY total_{metric} DESC
            """
            with engine.connect() as conn:
                result = conn.execute(text(query_str))
                return sanitize_rows([dict(row._mapping) for row in result])

        return await asyncio.to_thread(_execute)

    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise ValueError("cant join as no matching columns are found")

import asyncio
import pandas as pd
from app.core.database import engine
from app.services.analytics_sql import resolve_table_name
import math

async def _load_dataframe(dataset_uuid: str) -> pd.DataFrame:
    table_name = await resolve_table_name(dataset_uuid)
    def _fetch():
        query = f"SELECT * FROM {table_name}"
        return pd.read_sql(query, engine)
    return await asyncio.to_thread(_fetch)

def _clean_nan(data):
    """Recursively convert float NaN/Infinity to None and numpy types to python types for JSON serialization."""
    import numpy as np
    if isinstance(data, dict):
        return {k: _clean_nan(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_clean_nan(v) for v in data]
    elif isinstance(data, (float, np.floating)):
        val = float(data)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    elif isinstance(data, (int, np.integer)):
        return int(data)
    return data

async def calculate_rolling_average(dataset_uuid: str, target_col: str, window: int, sort_col: str = None):
    df = await _load_dataframe(dataset_uuid)
    
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' does not exist in dataset. Valid columns are: {list(df.columns)}")
    if sort_col and sort_col not in df.columns:
        raise ValueError(f"Sort column '{sort_col}' does not exist in dataset. Valid columns are: {list(df.columns)}")
    
    def _process():
        if sort_col:
            df_sorted = df.sort_values(by=sort_col).copy()
        else:
            df_sorted = df.copy()
            
        df_sorted[f"{target_col}_rolling_avg"] = df_sorted[target_col].rolling(window=window).mean()
        # Convert NaN to None for JSON serialization
        df_sorted = df_sorted.where(pd.notnull(df_sorted), None)
        return _clean_nan(df_sorted.to_dict(orient="records"))
        
    return await asyncio.to_thread(_process)

async def calculate_correlation_matrix(dataset_uuid: str, columns: list = None):
    df = await _load_dataframe(dataset_uuid)
    
    if columns:
        for col in columns:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' does not exist in dataset. Valid columns are: {list(df.columns)}")
    
    def _process():
        # Use specified columns or all numeric
        if columns:
            calc_df = df[columns]
        else:
            calc_df = df.select_dtypes(include='number')
            
        corr = calc_df.corr().round(4)
        corr = corr.where(pd.notnull(corr), None)
        return _clean_nan(corr.to_dict())
        
    return await asyncio.to_thread(_process)

async def detect_outliers(dataset_uuid: str, target_col: str):
    df = await _load_dataframe(dataset_uuid)
    
    def _process():
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' does not exist in dataset. Valid columns are: {list(df.columns)}")
        if not pd.api.types.is_numeric_dtype(df[target_col]):
            raise ValueError(f"Target column '{target_col}' must be numeric to perform outlier detection. Column type is: {df[target_col].dtype}")
            
        Q1 = df[target_col].quantile(0.25)
        Q3 = df[target_col].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outliers = df[(df[target_col] < lower_bound) | (df[target_col] > upper_bound)]
        outliers = outliers.where(pd.notnull(outliers), None)
        return _clean_nan({
            "bounds": {"lower": lower_bound, "upper": upper_bound},
            "outliers": outliers.to_dict(orient="records")
        })
        
    return await asyncio.to_thread(_process)

async def generate_categorical_profiles(dataset_uuid: str):
    df = await _load_dataframe(dataset_uuid)
    total_rows = len(df)
    
    if total_rows == 0:
        return {"detected_categorical_columns": [], "profiles": {}}
        
    def _process():
        detected_categorical_cols = []
        for col in df.columns:
            # Skip if ID-like column
            col_lower = col.lower()
            if col_lower == 'id' or col_lower.endswith('_id') or col_lower.endswith('uuid'):
                continue
                
            # Check string/object/category dtype
            is_cat_dtype = (
                pd.api.types.is_object_dtype(df[col]) or 
                pd.api.types.is_string_dtype(df[col]) or 
                df[col].dtype.name == 'category'
            )
            if is_cat_dtype:
                unique_values = df[col].nunique()
                unique_ratio = unique_values / total_rows
                # Low cardinality heuristic: ratio < 0.1 OR <= 15 unique values (to support small datasets)
                if unique_values > 1 and (unique_ratio < 0.1 or unique_values <= 15):
                    detected_categorical_cols.append(col)
                    
        numeric_cols = [
            c for c in df.columns 
            if pd.api.types.is_numeric_dtype(df[c]) and not (c.lower() == 'id' or c.lower().endswith('_id') or c.lower().endswith('uuid'))
        ]
        
        profiles = {}
        for cat_col in detected_categorical_cols:
            cat_profile = {}
            grouped = df.groupby(cat_col)
            for name, group in grouped:
                if pd.isnull(name):
                    name_str = "Unknown"
                else:
                    name_str = str(name)
                    
                group_stats = {
                    "record_count": int(len(group))
                }
                for num_col in numeric_cols:
                    mean_val = group[num_col].mean()
                    med_val = group[num_col].median()
                    min_val = group[num_col].min()
                    max_val = group[num_col].max()
                    
                    group_stats[f"avg_{num_col}"] = mean_val
                    group_stats[f"med_{num_col}"] = med_val
                    group_stats[f"min_{num_col}"] = min_val
                    group_stats[f"max_{num_col}"] = max_val
                    
                cat_profile[name_str] = group_stats
            profiles[cat_col] = cat_profile
            
        return {
            "detected_categorical_columns": detected_categorical_cols,
            "profiles": _clean_nan(profiles)
        }
        
    res = await asyncio.to_thread(_process)
    
    # Optionally store/cache profiles in MongoDB dataset registry
    try:
        from app.core.database import get_mongo_db
        mongo_db = get_mongo_db()
        await mongo_db.dataset_registry.update_one(
            {"dataset_uuid": dataset_uuid},
            {"$set": {"categorical_profiles": res}}
        )
    except Exception:
        # Don't fail the request if MongoDB cache update fails
        pass
        
    return res

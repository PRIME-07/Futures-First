import asyncio
import pandas as pd
from app.core.database import engine, get_mongo_db, create_external_engine
from app.services.analytics_sql import resolve_table_name, get_dataset_entry
import math

async def _load_dataframe(dataset_uuid: str) -> pd.DataFrame:
    """
    Load a DataFrame from the correct database source.
    Routes to the local staging engine for uploaded files or creates an
    ephemeral engine for external database connections.
    """
    entry = await get_dataset_entry(dataset_uuid)

    if entry.get("source_type") == "database":
        table_name = entry["external_table_name"]
        db_engine = create_external_engine(
            db_type=entry["external_db_type"],
            host=entry.get("external_host"),
            port=entry.get("external_port"),
            username=entry.get("external_username"),
            password=entry.get("external_password"),
            database_name=entry.get("external_database_name"),
        )
    else:
        table_name = entry["postgres_table_name"]
        db_engine = engine

    def _fetch():
        query = f"SELECT * FROM {table_name}"
        return pd.read_sql(query, db_engine)
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

async def calculate_rolling_average(
    dataset_uuid: str,
    target_col: str,
    window: int,
    sort_col: str = None,
    filter_dict: dict = None,
    pre_join: dict = None,
):
    """
    Compute a rolling average of `target_col` over `window` rows.

    Optional parameters:
      filter_dict  – {col: value} equality filters applied BEFORE the rolling window.
                     Supports temporal year-prefix matching (int in 1900–2100) and lists.
      pre_join     – {"right_uuid": "...", "on_key": "..."} — joins a dimension/lookup
                     table first so that filter_dict can reference columns (e.g. fuel_type)
                     that are not present in the primary dataset.
    """
    df = await _load_dataframe(dataset_uuid)

    # --- Optional pre-join with a dimension/lookup table ---
    if pre_join:
        right_uuid = pre_join.get("right_uuid")
        on_key = pre_join.get("on_key")
        if right_uuid and on_key:
            right_df = await _load_dataframe(right_uuid)
            left_on = next((c for c in df.columns if c.lower() == on_key.lower()), None)
            right_on = next((c for c in right_df.columns if c.lower() == on_key.lower()), None)
            if left_on and right_on:
                right_cols_to_keep = [right_on] + [
                    c for c in right_df.columns
                    if c != right_on and c not in df.columns
                ]
                df = df.merge(right_df[right_cols_to_keep], left_on=left_on, right_on=right_on, how="left")

    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' does not exist in dataset. Valid columns are: {list(df.columns)}")
    if sort_col and sort_col not in df.columns:
        raise ValueError(f"Sort column '{sort_col}' does not exist in dataset. Valid columns are: {list(df.columns)}")

    def _find_col(dataframe, name):
        if name in dataframe.columns:
            return name
        for c in dataframe.columns:
            if c.lower() == name.lower():
                return c
        return None

    def _process():
        working_df = df.copy()

        # --- Apply pre-filters ---
        TEMPORAL_KEYS = {"year", "month", "date", "period"}
        if filter_dict:
            for k, v in filter_dict.items():
                col = _find_col(working_df, k)
                if col is None:
                    continue
                if k.lower() in TEMPORAL_KEYS and isinstance(v, int) and 1900 < v < 2100:
                    working_df = working_df[working_df[col].astype(str).str.startswith(str(v))]
                elif isinstance(v, (list, tuple)):
                    working_df = working_df[
                        working_df[col].astype(str).str.lower().isin([str(item).lower() for item in v])
                    ]
                else:
                    working_df = working_df[
                        working_df[col].astype(str).str.lower() == str(v).lower()
                    ]

        if working_df.empty:
            raise ValueError(
                f"Rolling average dataset is empty after applying filters: {filter_dict}. "
                f"Check that filter values match the data."
            )

        if sort_col:
            working_df = working_df.sort_values(by=sort_col)

        working_df[f"{target_col}_rolling_avg"] = working_df[target_col].rolling(window=window).mean()
        working_df = working_df.where(pd.notnull(working_df), None)
        return _clean_nan(working_df.to_dict(orient="records"))

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
        
        outliers_mask = (df[target_col] < lower_bound) | (df[target_col] > upper_bound)
        outliers = df[outliers_mask].where(pd.notnull(df[outliers_mask]), None)

        # Build chart_data: full context series with IQR bounds + anomaly flag per row
        chart_df = df.copy()
        chart_df["lower_bound"] = round(lower_bound, 4)
        chart_df["upper_bound"] = round(upper_bound, 4)
        chart_df["is_outlier"] = outliers_mask
        chart_df = chart_df.where(pd.notnull(chart_df), None)
        
        return _clean_nan({
            "method": "IQR",
            "metric": target_col,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "outlier_count": len(outliers),
            "distribution_summary": {
                "mean": df[target_col].mean(),
                "median": df[target_col].median(),
                "std_dev": df[target_col].std()
            },
            "outliers": outliers.to_dict(orient="records"),
            "chart_data": chart_df.to_dict(orient="records")
        })
        
    return await asyncio.to_thread(_process)

def _try_align_series(series1: pd.Series, series2: pd.Series):
    """
    Attempt to align two series representing join keys.
    Returns: (aligned_series1, aligned_series2, alignment_type)
    Where alignment_type is 'temporal_yearly', 'temporal_monthly', 'temporal_daily',
    'categorical_case_insensitive', 'categorical_fuzzy', or 'exact'.
    """
    # 1. Check if both can be parsed as datetimes (temporal)
    try:
        # Check if the series values look date-like
        def is_datetime_like(s):
            if pd.api.types.is_datetime64_any_dtype(s):
                return True
            sample = s.dropna().head(10).astype(str)
            if sample.empty:
                return False
            import re
            date_patterns = [
                r'^\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
                r'^\d{4}-\d{2}',        # YYYY-MM
                r'^\d{4}/\d{2}',        # YYYY/MM
                r'^\d{4}$',             # YYYY
            ]
            return any(any(re.search(pat, val) for pat in date_patterns) for val in sample)

        if is_datetime_like(series1) and is_datetime_like(series2):
            dt1 = pd.to_datetime(series1, errors='coerce')
            dt2 = pd.to_datetime(series2, errors='coerce')

            def detect_freq(dt_series):
                non_null = dt_series.dropna()
                if non_null.empty:
                    return 'Y'
                days = non_null.dt.day.unique()
                months = non_null.dt.month.unique()
                # A series of the form YYYY-01-01 (all day=1, all month=1) → yearly
                if len(days) == 1 and days[0] == 1 and len(months) == 1 and months[0] == 1:
                    return 'Y'
                # A series of the form YYYY-MM-01 (all day=1, mixed months) → monthly
                if len(days) == 1 and days[0] == 1:
                    return 'M'
                # Any variation in day → daily (but we still coerce to YYYY-MM for safety)
                return 'D'

            f1 = detect_freq(dt1)
            f2 = detect_freq(dt2)

            # Use the coarser of the two granularities so both series align.
            # Crucially: both Daily and Monthly → normalize to YYYY-MM so that
            # a dataset with '2022-01-15' aligns with one storing '2022-01'.
            coarser = 'Y' if ('Y' in (f1, f2)) else 'M'

            if coarser == 'Y':
                return dt1.dt.year.astype(str), dt2.dt.year.astype(str), 'temporal_yearly'
            else:
                # Both monthly and daily series are collapsed to YYYY-MM grain
                return dt1.dt.strftime('%Y-%m'), dt2.dt.strftime('%Y-%m'), 'temporal_monthly'
    except Exception:
        pass

    # 2. Categorical / Fuzzy String normalizer
    s1_clean = series1.astype(str).str.lower().str.strip()
    s2_clean = series2.astype(str).str.lower().str.strip()
    
    overlap = set(s1_clean).intersection(set(s2_clean))
    if overlap:
        return s1_clean, s2_clean, 'categorical_case_insensitive'
        
    s1_unique = series1.dropna().unique()
    s2_unique = series2.dropna().unique()
    mapping = {}
    for val1 in s1_unique:
        v1_clean = str(val1).lower().strip()
        if not v1_clean:
            continue
        for val2 in s2_unique:
            v2_clean = str(val2).lower().strip()
            if not v2_clean:
                continue
            if v1_clean in v2_clean or v2_clean in v1_clean:
                mapping[val1] = val2
                break
                
    if mapping:
        mapped_s1 = series1.map(mapping).fillna(series1)
        return mapped_s1.astype(str).str.strip(), series2.astype(str).str.strip(), 'categorical_fuzzy'

    return series1.astype(str).str.strip(), series2.astype(str).str.strip(), 'exact'


def _determine_agg_func(metric_name: str) -> str:
    """
    Heuristic to determine if a metric should be aggregated via SUM or MEAN.
    SUM: counts, units, volume, revenue, clicks, views, cost, spend.
    MEAN: rates, averages, prices, percentages, ratios, margins, ctr, roi, interest_rate.
    """
    m_lower = metric_name.lower()
    mean_keywords = {
        "price", "rate", "pct", "percent", "percentage", "ratio", "margin", 
        "ctr", "roi", "average", "avg", "cost_per", "cpc", "cpm", "interest"
    }
    if any(k in m_lower for k in mean_keywords):
        return "mean"
    return "sum"


async def multi_dataset_join_analysis(
    datasets: list,
    join_key: str,
) -> dict:
    """
    Universal N-way multi-dataset join and correlation engine.

    Each entry in `datasets` is a dict with:
      - dataset_uuid (required)
      - metric (required): column to aggregate
      - label (optional): human-readable name for this metric
      - filter_dict (optional): {col: value} equality filters applied before aggregation
      - filter_dict_exclude (optional): {col: value} inequality (!=) filters
      - pre_join (optional): {right_uuid, on_key} — join with a lookup/dim table first
        to inherit extra columns (e.g. join monthly_sales with car_models on model_id
        to then filter by fuel_type)
      - agg_func (optional): "sum" or "mean" — overrides the heuristic

    join_key: the shared column to group/join all datasets on.
      Can be temporal (month, year, date) or categorical (movie_id, product_id, model_id).
    """

    async def _load_and_prepare(descriptor: dict) -> pd.DataFrame:
        df = await _load_dataframe(descriptor["dataset_uuid"])

        # Step 1: Pre-join with a lookup/dimension table if specified
        pre_join = descriptor.get("pre_join")
        if pre_join:
            right_uuid = pre_join.get("right_uuid")
            on_key = pre_join.get("on_key")
            if right_uuid and on_key:
                right_df = await _load_dataframe(right_uuid)
                # Case-insensitive column matching for on_key
                left_on = next((c for c in df.columns if c.lower() == on_key.lower()), None)
                right_on = next((c for c in right_df.columns if c.lower() == on_key.lower()), None)
                if left_on and right_on:
                    # Drop duplicate columns from right_df except the join key
                    right_cols_to_keep = [right_on] + [
                        c for c in right_df.columns
                        if c != right_on and c not in df.columns
                    ]
                    df = df.merge(right_df[right_cols_to_keep], left_on=left_on, right_on=right_on, how="left")

        return df

    # Load all datasets (concurrently)
    loaded_frames = await asyncio.gather(*[_load_and_prepare(d) for d in datasets])

    def _process():
        def find_col(df, name):
            if name in df.columns:
                return name
            for c in df.columns:
                if c.lower() == name.lower():
                    return c
            return None

        aggregated_frames = []
        metric_names = []
        metric_labels = []

        for i, (descriptor, df) in enumerate(zip(datasets, loaded_frames)):
            metric = descriptor["metric"]
            label = descriptor.get("label") or metric
            override_agg = descriptor.get("agg_func")

            # --- Equality filters ---
            filter_dict = descriptor.get("filter_dict") or {}
            for k, v in filter_dict.items():
                col = find_col(df, k)
                if col:
                    if k.lower() in ("year", "month", "date", "period") and isinstance(v, int) and 1900 < v < 2100:
                        df = df[df[col].astype(str).str.startswith(str(v))]
                    elif isinstance(v, (list, tuple)):
                        df = df[df[col].astype(str).str.lower().isin([str(item).lower() for item in v])]
                    else:
                        df = df[df[col].astype(str).str.lower() == str(v).lower()]

            # --- Exclusion filters ---
            filter_dict_exclude = descriptor.get("filter_dict_exclude") or {}
            for k, v in filter_dict_exclude.items():
                col = find_col(df, k)
                if col:
                    if isinstance(v, (list, tuple)):
                        df = df[~df[col].astype(str).str.lower().isin([str(item).lower() for item in v])]
                    else:
                        df = df[df[col].astype(str).str.lower() != str(v).lower()]

            if df.empty:
                raise ValueError(
                    f"Dataset {i+1} ('{label}') is empty after applying filters. "
                    f"Check filter_dict / filter_dict_exclude values."
                )

            # --- Detect join key and metric columns ---
            jk_col = find_col(df, join_key)
            if not jk_col:
                raise ValueError(
                    f"Join key '{join_key}' not found in dataset {i+1} ('{label}'). "
                    f"Available columns: {list(df.columns)}"
                )
            m_col = find_col(df, metric)
            if not m_col:
                raise ValueError(
                    f"Metric '{metric}' not found in dataset {i+1} ('{label}'). "
                    f"Available columns: {list(df.columns)}"
                )

            # --- Aggregation ---
            agg_func = override_agg or _determine_agg_func(m_col)
            agg_df = df.groupby(jk_col, as_index=False)[m_col].agg(agg_func)

            # Rename metric to a deduplicated name if multiple datasets share the same metric name
            safe_metric_name = m_col if m_col not in metric_names else f"{m_col}_{i+1}"
            agg_df = agg_df.rename(columns={m_col: safe_metric_name, jk_col: "__join_key__"})

            aggregated_frames.append(agg_df)
            metric_names.append(safe_metric_name)
            metric_labels.append(label)

        # --- Align temporal keys across all frames ---
        # Use _try_align_series pairwise on the first two to detect the alignment type,
        # then apply the same normalization to all frames uniformly.
        alignment_type = "exact"
        if len(aggregated_frames) >= 2:
            s1 = aggregated_frames[0]["__join_key__"]
            s2 = aggregated_frames[1]["__join_key__"]
            aligned_s1, aligned_s2, alignment_type = _try_align_series(s1, s2)
            aggregated_frames[0]["__join_key__"] = aligned_s1
            aggregated_frames[1]["__join_key__"] = aligned_s2

            # Apply the same detected normalization to remaining frames
            for j in range(2, len(aggregated_frames)):
                s_j = aggregated_frames[j]["__join_key__"]
                try:
                    if "temporal_yearly" in alignment_type:
                        aggregated_frames[j]["__join_key__"] = pd.to_datetime(s_j, errors="coerce").dt.year.astype(str)
                    elif "temporal_monthly" in alignment_type:
                        aggregated_frames[j]["__join_key__"] = pd.to_datetime(s_j, errors="coerce").dt.strftime("%Y-%m")
                    elif "temporal_daily" in alignment_type:
                        aggregated_frames[j]["__join_key__"] = pd.to_datetime(s_j, errors="coerce").dt.strftime("%Y-%m-%d")
                    else:
                        aggregated_frames[j]["__join_key__"] = s_j.astype(str).str.lower().str.strip()
                except Exception:
                    pass

        # --- Iterative inner merge ---
        merged = aggregated_frames[0]
        for frame in aggregated_frames[1:]:
            merged = pd.merge(merged, frame, on="__join_key__", how="inner")

        if merged.empty:
            # Provide helpful debug info
            previews = {
                f"dataset_{i+1}_{metric_names[i]}": list(aggregated_frames[i]["__join_key__"].head(5))
                for i in range(len(aggregated_frames))
            }
            raise ValueError(
                f"Multi-join produced an empty result after merging {len(datasets)} datasets on '{join_key}'. "
                f"Key previews per dataset: {previews}. "
                f"Verify that the join_key column name and its values overlap across all datasets."
            )

        merged = merged.rename(columns={"__join_key__": join_key})

        # --- N×N Correlation matrix ---
        corr_matrix = {}
        if len(metric_names) >= 2:
            corr_df = merged[metric_names].corr().round(4)
            corr_df = corr_df.where(pd.notnull(corr_df), None)
            corr_matrix = _clean_nan(corr_df.to_dict())

        # --- Archetype classification ---
        is_temporal = "temporal" in alignment_type
        archetype = "temporal" if is_temporal else "categorical"
        artifact_type = "multi_join_timeseries" if is_temporal else "multi_join_categorical"

        return _clean_nan({
            "artifact_type": artifact_type,
            "join_key": join_key,
            "join_archetype": archetype,
            "alignment_type": alignment_type,
            "n_datasets": len(datasets),
            "post_join_rows": len(merged),
            "metrics": metric_names,
            "labels": metric_labels,
            "correlation_matrix": corr_matrix,
            "data": merged.to_dict(orient="records"),
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

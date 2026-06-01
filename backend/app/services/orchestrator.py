import json
import logging
import time
import asyncio
from typing import Dict, Any, List
from openai import AsyncOpenAI
import os
import sys
from app.core.database import get_mongo_db
from app.core.config import settings
from app.services.synthesis import MultiSourceAggregator, wrap_engine_call
from app.services import analytics_sql, analytics_pandas, rag_engine

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("OpenAI API key not provided")
    sys.exit(1)

client = AsyncOpenAI(api_key=api_key)

logger = logging.getLogger(__name__)

async def get_session_schema_context(session_id: str) -> str:
    db = get_mongo_db()
    cursor = db.dataset_registry.find({"session_id": session_id})
    datasets = await cursor.to_list(length=None)

    if not datasets:
        return "No structured datasets uploaded yet."

    # Collect categorical sample values from actual data for low-cardinality columns
    # so the LLM generates exact filter values that match the data (e.g. "West" not "West Coast")
    from app.services import analytics_pandas as _ap
    async def _get_sample_values(ds: dict) -> dict:
        """Return {col: [distinct_values]} for low-cardinality categorical columns."""
        try:
            df = await _ap._load_dataframe(ds["dataset_uuid"])
            result = {}
            for col, meta in ds.get("semantic_mapping", {}).items():
                if meta.get("role") != "dimension":
                    continue
                if col not in df.columns:
                    continue
                # Only include columns with ≤15 distinct values to avoid token bloat
                unique_vals = df[col].dropna().unique()
                if len(unique_vals) <= 15:
                    result[col] = sorted([str(v) for v in unique_vals])
            return result
        except Exception:
            return {}

    import asyncio as _asyncio
    sample_values_list = await _asyncio.gather(*[_get_sample_values(ds) for ds in datasets])

    context = "Available Datasets:\n"
    for ds, sample_vals in zip(datasets, sample_values_list):
        source_type = ds.get("source_type", "uploaded")
        source_label = "[External DB]" if source_type == "database" else "[Uploaded File]"
        display_name = ds.get("original_filename") or ds.get("dataset_name", "unknown")
        context += f"- {source_label} {display_name}\n"
        context += f"  dataset_uuid: {ds.get('dataset_uuid')}\n"
        semantics = ds.get("semantic_mapping", {})
        columns = list(semantics.keys()) if semantics else ds.get("columns", [])
        context += f"  Columns (Enum): {columns}\n"
        context += f"  Columns and roles: {json.dumps(semantics)}\n"
        if sample_vals:
            context += f"  Categorical valid values (use EXACTLY these in filter_dict): {json.dumps(sample_vals)}\n"
    return context

async def fetch_chat_history_with_token_limit(session_id: str, max_tokens: int = 500) -> List[Dict[str, str]]:
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        encoding = None

    db = get_mongo_db()
    cursor = db.chats.find({"session_id": session_id}).sort("timestamp", -1).limit(15)
    chats = await cursor.to_list(length=None)
    
    formatted_messages = []
    current_tokens = 0
    
    for chat in chats:
        u_text = chat.get("query", "")
        a_text = chat.get("answer", "")
        if not u_text or not a_text:
            continue
            
        exchange_text = f"user\n{u_text}\nassistant\n{a_text}\n"
        if encoding:
            tokens_count = len(encoding.encode(exchange_text))
        else:
            tokens_count = len(exchange_text) // 4
            
        if current_tokens + tokens_count > max_tokens:
            break
            
        current_tokens += tokens_count
        formatted_messages.insert(0, {"role": "assistant", "content": a_text})
        formatted_messages.insert(0, {"role": "user", "content": u_text})
        
    return formatted_messages

async def classify_intent_and_extract_parameters(query: str, session_id: str, on_retry=None) -> Dict[str, Any]:
    schema_context = await get_session_schema_context(session_id)
    
    system_prompt = f"""You are the orchestration brain of Insight Monkey.
Your task is to analyze the user's query and output a structured JSON command that maps to our precise analytical endpoints.

{schema_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 0 — MARKET SHARE / BREAKDOWN ROUTING (HIGHEST PRIORITY — READ BEFORE ALL OTHER RULES)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If the user asks for ANY of the following:
  • "market share", "share of", "proportion of", "percentage of", "distribution of"
  • "which X sold how much", "top X by Y", "revenue/sales by brand/genre/category"
  • "contribution of each", "breakdown of", "composition of"
  • "what sold the most", "units sold per brand/model"
  • AND a specific time filter ("in 2022", "last year", "Q1", etc.)

THEN you MUST use:
  → "sql_aggregate" — if the metric AND group_by are both in the SAME table.
  → "sql_join_aggregate" — if the metric is in one table (e.g. monthly_sales.units_sold) and the grouping dimension is in a RELATED table (e.g. car_models.brand), joined by a shared key (e.g. model_id). Pass filter_dict with the year integer (e.g. {{"month": 2022}}) to filter.

YOU MUST NEVER USE "pandas_multi_join" for share/breakdown/market-share queries.
pandas_multi_join is EXCLUSIVELY for correlating two independent time-series metrics from SEPARATE datasets (e.g. "do EV sales correlate with fuel prices over time?").

EXAMPLE — CORRECT ROUTING:
  Query: "market share of which vehicle sold how much in 2022"
  → sql_join_aggregate: left=monthly_sales (metric: units_sold), right=car_models (group_by: brand), join_key: model_id, filter_dict: {{"month": 2022}}, chart_hint: "pie"

  Query: "which genre had the highest viewership share"
  → sql_join_aggregate: left=streaming_metrics (metric: unique_viewers), right=movies (group_by: genre), join_key: movie_id, chart_hint: "pie"

EXAMPLE — WRONG ROUTING (NEVER DO THIS FOR SHARE QUERIES):
  ✗ pandas_multi_join for "market share of vehicles in 2022" — THIS IS WRONG
  ✗ pandas_multi_join for "which brand sold the most" — THIS IS WRONG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL RULES:
1. You MUST output a JSON object containing exactly one key: "tool_calls", which is a list of tool execution plans.
2. BI & VISUALIZATION MANDATE: Every business intelligence or data analytics query MUST have an accompanying chart to support its reasoning. Therefore, for any query that is analytical in nature, you MUST call at least one structured data tool (e.g. `sql_aggregate`, `pandas_categorical_profiles`, `pandas_correlation`, `pandas_rolling_average`, etc.) that fetches relevant numeric/categorical data, even if you also call `rag_retrieve` for document lookup. Never call `rag_retrieve` in isolation for analytical queries; always pair it with a structured tool call so that a chart can be generated.
3. CAPABILITY-DRIVEN ROUTING: Review the capabilities of each intent below. Based on the user's query, dynamically decide which specific tools and datasets will provide the best analytical evidence. Deploy ONLY the tools needed to answer the query; do not spam unrelated datasets.
4. IMPLICIT CROSS-DATASET CORRELATION: You must act as an expert analyst. If answering a correlation or trend question requires bridging metrics across different datasets over a SHARED TIME AXIS, use `pandas_multi_join`. HOWEVER — if the question is about SHARE/BREAKDOWN/MARKET-SHARE, see RULE 0 above — those must use sql_aggregate or sql_join_aggregate, NOT pandas_multi_join.
5. TEXT COLUMN LIMITATION: Never run `sql_aggregate` or `sql_join_aggregate` with a text/categorical column (like genre, title, brand, language, country) as the 'metric' parameter. Text columns cannot be aggregated via SUM; they can only be used as 'group_by' or in filters.
6. Each object in "tool_calls" MUST contain EXACTLY three keys: "intent", "parameters", and "chart_hint".
   - "chart_hint" is your authoritative declaration of the best chart type for this tool call's result. Choose from:
     * "pie"      — Use when the query asks for share, proportion, distribution, composition, or percentage breakdown of a whole (e.g. 'what is each genre's share of total viewership', 'revenue split by region', 'what percentage of sales comes from each channel').
     * "line"     — Use when the result is a single metric over time (trend, growth, trajectory).
     * "composed" — Use when the result has two or more metrics over time with different scales (multi-axis time series).
     * "bar"      — Use when comparing magnitudes across categories where share/proportion is NOT the intent (e.g. 'top 5 genres by revenue', 'average rating by platform').
     * "auto"     — Use only when none of the above clearly applies; the chart agent will apply heuristics as a fallback.
   - CRITICAL: If the user's question contains words like 'share', 'proportion', 'percentage', 'breakdown', 'distribution', 'composition', 'what portion', 'what fraction', 'how much of the total' — the chart_hint MUST be "pie".
7. The "intent" MUST be exactly ONE of the following:
   - "sql_aggregate": Best for finding totals, maximums, minimums, or grouping metrics by a dimension (like month or genre).
   - "sql_join_aggregate": Use when you need to sum/aggregate a metric from one table (e.g., unique_viewers, watch_hours) grouped by a dimension from a different table (e.g., genre, language) in the same database, joining them on their shared key (e.g., movie_id).
   - "pandas_rolling_average": Best for smoothing time-series trends over a window.
   - "pandas_correlation": Best for finding mathematical correlation coefficients between numerical columns within a SINGLE table.
   - "pandas_multi_join": ONLY for correlating metrics across 2 or more SEPARATE datasets over a shared TIME AXIS. Use when:
     (a) a query requires filtering by a sub-segment before correlating (e.g. 'only EV cars', 'only Sci-Fi films', 'only Electronics category'),
     (b) more than two datasets are needed simultaneously,
     (c) the join key is a temporal axis (month/date) and you are comparing TRENDS not SHARES.
     DO NOT USE for market share, breakdown, or composition queries — see RULE 0.
   - "pandas_outliers": Best for detecting anomalies, spikes, or extreme values in a numeric column.
   - "pandas_categorical_profiles": Best for comparing performance or distributions across categorical segments (e.g., platform, campaign_type).
   - "rag_retrieve": Best for answering questions about strategy, rules, guidelines, or extracting insights from unstructured text/PDFs.
7. The "parameters" object MUST be populated based on the chosen intent, using the exact `dataset_uuid` and exact Enum column names defined in the Available Datasets above.

REQUIRED PARAMETERS FOR EACH INTENT:
- "sql_aggregate": {{"dataset_uuid": "...", "metric": "...", "group_by": "...", "filter_dict": {{}}}}
- "sql_join_aggregate": {{"left_dataset_uuid": "...", "right_dataset_uuid": "...", "join_key": "...", "metric": "...", "group_by": "...", "filter_dict": {{}}}}
- "pandas_rolling_average": {{"dataset_uuid": "...", "target_col": "...", "window": 7, "sort_col": "...", "filter_dict": {{}}, "pre_join": {{"right_uuid": "...", "on_key": "..."}}}}
  Note: filter_dict and pre_join are OPTIONAL. Use them when the rolling average must be restricted to a sub-segment (e.g. Hybrid models only). pre_join works exactly like in pandas_multi_join — join a dimension table first so filter_dict can reference columns like fuel_type that are absent in the primary fact table.
- "pandas_correlation": {{"dataset_uuid": "...", "columns": ["...", "..."]}}
- "pandas_multi_join": {{
    "datasets": [
      {{"dataset_uuid": "...", "metric": "...", "label": "...", "filter_dict": {{}}, "filter_dict_exclude": {{}}, "pre_join": {{"right_uuid": "...", "on_key": "..."}}}},
      {{"dataset_uuid": "...", "metric": "...", "label": "..."}}
    ],
    "join_key": "month"
  }}
- "pandas_outliers": {{"dataset_uuid": "...", "target_col": "..."}}
- "pandas_categorical_profiles": {{"dataset_uuid": "..."}}
- "rag_retrieve": {{}} (no dataset_uuid required)

ROLLING AVERAGE SUB-SEGMENT RULE (read before MULTI-JOIN DECISION TREE):
- If the user asks for a "smoothed trend", "rolling average", "moving average", or "trend line" for a SPECIFIC SUB-SEGMENT (e.g. Hybrid models, Action films, Electronics category):
  → ALWAYS use "pandas_rolling_average" with filter_dict (and pre_join if the filter column is in a dimension table).
  → NEVER use pandas_multi_join for a single-metric rolling/smoothed trend query.
  EXAMPLE — CORRECT:
    Query: "smoothed trend line of monthly sales for Hybrid models"
    → pandas_rolling_average: dataset=monthly_sales, target_col=units_sold, window=3, sort_col=month,
      pre_join={{right_uuid: car_models_uuid, on_key: model_id}}, filter_dict={{"fuel_type": "Hybrid"}}
  EXAMPLE — WRONG:
    ✗ pandas_multi_join for "smoothed trend for Hybrid" — THIS IS WRONG

PRE-JOIN FILTER RULE:
- When you use pre_join on a descriptor (in either pandas_multi_join OR pandas_rolling_average), the pre_join is done so that you can FILTER by a column from the dimension table.
- You MUST set filter_dict on that same descriptor to include the filter that motivated the pre_join.
- EXAMPLE — CORRECT:
    pre_join: {{right_uuid: car_models_uuid, on_key: model_id}}, filter_dict: {{"fuel_type": "Electric"}}
- EXAMPLE — WRONG:
    pre_join: {{right_uuid: car_models_uuid, on_key: model_id}}, filter_dict: {{}}   ← THIS IS WRONG (pre_join with no filter is pointless)

MULTI-JOIN DECISION TREE — when to use pandas_multi_join:
- User wants to CORRELATE or COMPARE metrics (including ratios, yield, ROI, or efficiencies) from SEPARATE datasets over a shared axis (temporal or entity) → pandas_multi_join.
- User asks about 3 or more datasets simultaneously in a correlation/comparison context → pandas_multi_join.
- User asks about a FILTERED sub-segment that requires joining with a lookup table first (filtering a fact table by a dimension present only in a lookup table) → pandas_multi_join with filter_dict and pre_join.
- If dimensions (like platform or category) need to be aligned across datasets that only share a record identifier (entity key), set the join_key to that shared entity identifier.
- filter_dict: {{col: value}} for equality filters.
- filter_dict_exclude: {{col: value}} for inequality filters.
- pre_join: use when the primary fact table lacks a needed filter column and must inherit it from a dimension table first.

Note: For pandas_outliers and sql_aggregate/rolling_average 'metric' or 'target_col', ensure the column role is "metric".
"""

    history = await fetch_chat_history_with_token_limit(session_id, max_tokens=500)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": query})

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=settings.MODEL_NAME,
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            raw_output = response.choices[0].message.content
            parsed_output = json.loads(raw_output)
            
            if "tool_calls" not in parsed_output:
                if attempt < max_retries:
                    msg = f"Model generated a malformed output! Retrying... (Attempt {attempt + 1}/{max_retries})"
                    logger.warning(msg)
                    if on_retry:
                        await on_retry(attempt + 1, max_retries, "malformed")
                    messages.append({"role": "assistant", "content": raw_output})
                    messages.append({"role": "user", "content": "You missed the 'tool_calls' key. Please output the JSON strictly adhering to the schema requested."})
                    continue
                else:
                    logger.error("Max retries reached for malformed output.")
                    return {"tool_calls": [{"intent": "rag_retrieve", "parameters": {}}]}
                    
            return parsed_output
            
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                msg = f"Model generated invalid JSON! Retrying... (Attempt {attempt + 1}/{max_retries})"
                logger.warning(msg)
                if on_retry:
                    await on_retry(attempt + 1, max_retries, "invalid_json")
                continue
            logger.error(f"Classification JSON parsing failed: {str(e)}")
            return {"tool_calls": [{"intent": "rag_retrieve", "parameters": {}}]}
            
        except Exception as e:
            logger.error(f"Classification failed: {str(e)}")
            return {"tool_calls": [{"intent": "rag_retrieve", "parameters": {}}]}
            
    return {"tool_calls": [{"intent": "rag_retrieve", "parameters": {}}]}

async def orchestrate_pipeline(query: str, session_id: str, aggregator: MultiSourceAggregator, on_retry=None) -> List[Dict[str, Any]]:
    """
    Runs classification, executes multiple tools in parallel wrapped in telemetry, and adds them to the aggregator.
    Returns a list of telemetry dicts to stream back to the UI.
    """
    plan = await classify_intent_and_extract_parameters(query, session_id, on_retry=on_retry)
    tool_calls = plan.get("tool_calls", [])

    # ── DEBUG: log the orchestrator's full decision plan ──────────────────────
    import sys
    print(f"[ORCHESTRATOR PLAN] query={query!r}  tool_calls={json.dumps(tool_calls, indent=2)}", flush=True, file=sys.stdout)
    # ─────────────────────────────────────────────────────────────────────────

    if not tool_calls:
        tool_calls = [{"intent": "rag_retrieve", "parameters": {}}]

    async def execute_tool(tool_call: Dict[str, Any]) -> Dict[str, Any]:
        intent = tool_call.get("intent")
        params = tool_call.get("parameters", {})
        chart_hint = tool_call.get("chart_hint", "auto")  # authoritative viz type from the orchestrator LLM
        dataset_uuid = params.get("dataset_uuid") or params.get("left_dataset_uuid")
        
        try:
            if intent == "sql_aggregate":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_sql.run_aggregation,
                    dataset_uuid, params.get("metric"), params.get("group_by"), params.get("filter_dict")
                )
                res["chart_hint"] = chart_hint
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "sql_join_aggregate":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_sql.run_join_aggregation,
                    params.get("left_dataset_uuid"), params.get("right_dataset_uuid"),
                    params.get("join_key"), params.get("metric"), params.get("group_by"),
                    params.get("filter_dict")
                )
                res["chart_hint"] = chart_hint
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_rolling_average":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_pandas.calculate_rolling_average,
                    dataset_uuid,
                    params.get("target_col"),
                    params.get("window", 7),
                    params.get("sort_col"),
                    params.get("filter_dict"),
                    params.get("pre_join"),
                )
                res["chart_hint"] = chart_hint
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_correlation":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_pandas.calculate_correlation_matrix,
                    dataset_uuid, params.get("columns")
                )
                res["chart_hint"] = chart_hint
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_multi_join":
                res = await wrap_engine_call(
                    intent,
                    (params.get("datasets") or [{}])[0].get("dataset_uuid"),
                    analytics_pandas.multi_dataset_join_analysis,
                    params.get("datasets", []),
                    params.get("join_key", "month")
                )
                res["chart_hint"] = chart_hint
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_outliers":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_pandas.detect_outliers,
                    dataset_uuid, params.get("target_col")
                )
                res["chart_hint"] = chart_hint
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_categorical_profiles":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_pandas.generate_categorical_profiles,
                    dataset_uuid
                )
                res["chart_hint"] = chart_hint
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "rag_retrieve" or not intent:
                rag_start = time.time()
                rag_res = await rag_engine.retrieve_context(session_id, query)
                rag_duration = int((time.time() - rag_start) * 1000)
                
                if rag_res:
                    aggregator.add_rag_contexts(rag_res)
                    return {
                        "tool_name": "rag_search",
                        "original_filename": "Multiple PDFs",
                        "duration_ms": rag_duration,
                        "status": "success",
                        "row_count": len(rag_res),
                        "preview": str([r.get("filename") for r in rag_res])
                    }
                else:
                    return {
                        "tool_name": "rag_search",
                        "original_filename": "Multiple PDFs",
                        "duration_ms": rag_duration,
                        "status": "success",
                        "row_count": 0,
                        "preview": "No contexts found."
                    }
        except Exception as e:
            logger.error("[ORCHESTRATOR TOOL ERROR] intent=%r error=%s", intent, str(e))
            return {
                "tool_name": intent,
                "original_filename": "N/A",
                "duration_ms": 0,
                "status": "error",
                "row_count": 0,
                "preview": "",
                "error": str(e)
            }
        return {}

    # Execute all tools in parallel concurrently!
    telemetries = await asyncio.gather(*[execute_tool(tc) for tc in tool_calls])
    return list(telemetries)

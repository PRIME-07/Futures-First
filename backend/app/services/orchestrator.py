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
        
    context = "Available Datasets:\n"
    for ds in datasets:
        context += f"- original_filename: {ds.get('filename')}\n"
        context += f"  dataset_uuid: {ds.get('dataset_uuid')}\n"
        semantics = ds.get("semantic_mapping", {})
        columns = list(semantics.keys()) if semantics else ds.get("columns", [])
        context += f"  Columns (Enum): {columns}\n"
        context += f"  Columns and roles: {json.dumps(semantics)}\n"
    return context

async def classify_intent_and_extract_parameters(query: str, session_id: str, on_retry=None) -> Dict[str, Any]:
    schema_context = await get_session_schema_context(session_id)
    
    system_prompt = f"""You are the orchestration brain of Insight Monkey.
Your task is to analyze the user's query and output a structured JSON command that maps to our precise analytical endpoints.

{schema_context}

CRITICAL RULES:
1. You MUST output a JSON object containing exactly one key: "tool_calls", which is a list of tool execution plans.
2. CAPABILITY-DRIVEN ROUTING: Review the capabilities of each intent below. Based on the user's query, dynamically decide which specific tools and datasets will provide the best analytical evidence. Deploy ONLY the tools needed to answer the query; do not spam unrelated datasets.
3. IMPLICIT CROSS-DATASET CORRELATION: You must act as an expert analyst. Even if the user doesn't explicitly ask you to "correlate" or "compare", if answering their broad ecosystem question requires bridging metrics across different datasets, you MUST proactively deploy tools to fetch both. DO NOT use `sql_join_aggregate` for this. Instead, output MULTIPLE separate `sql_aggregate` tools (one for each dataset) in parallel, grouping them by a common dimension (e.g., 'month' or 'movie_id'). The synthesis engine will handle the final correlation.
4. Each object in "tool_calls" MUST contain EXACTLY two keys: "intent" and "parameters".
5. The "intent" MUST be exactly ONE of the following:
   - "sql_aggregate": Best for finding totals, maximums, minimums, or grouping metrics by a dimension (like month or genre).
   - "sql_join_aggregate": Use ONLY if a single metric needs to be summed after joining two tables.
   - "pandas_rolling_average": Best for smoothing time-series trends over a window.
   - "pandas_correlation": Best for finding mathematical correlation coefficients between numerical columns within a SINGLE table.
   - "pandas_outliers": Best for detecting anomalies, spikes, or extreme values in a numeric column.
   - "pandas_categorical_profiles": Best for comparing performance or distributions across categorical segments (e.g., platform, campaign_type).
   - "rag_retrieve": Best for answering questions about strategy, rules, guidelines, or extracting insights from unstructured text/PDFs.
6. The "parameters" object MUST be populated based on the chosen intent, using the exact `dataset_uuid` and exact Enum column names defined in the Available Datasets above.

REQUIRED PARAMETERS FOR EACH INTENT:
- "sql_aggregate": {{"dataset_uuid": "...", "metric": "...", "group_by": "...", "filter_dict": {{}}}}
- "sql_join_aggregate": {{"left_dataset_uuid": "...", "right_dataset_uuid": "...", "join_key": "...", "metric": "...", "group_by": "..."}}
- "pandas_rolling_average": {{"dataset_uuid": "...", "target_col": "...", "window": 7, "sort_col": "..."}}
- "pandas_correlation": {{"dataset_uuid": "...", "columns": ["...", "..."]}}
- "pandas_outliers": {{"dataset_uuid": "...", "target_col": "..."}}
- "pandas_categorical_profiles": {{"dataset_uuid": "..."}}
- "rag_retrieve": {{}} (no dataset_uuid required)

Note: For pandas_outliers and sql_aggregate/rolling_average 'metric' or 'target_col', ensure the column role is "metric".
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]

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
        
    if not tool_calls:
        tool_calls = [{"intent": "rag_retrieve", "parameters": {}}]

    async def execute_tool(tool_call: Dict[str, Any]) -> Dict[str, Any]:
        intent = tool_call.get("intent")
        params = tool_call.get("parameters", {})
        dataset_uuid = params.get("dataset_uuid") or params.get("left_dataset_uuid")
        
        try:
            if intent == "sql_aggregate":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_sql.run_aggregation,
                    dataset_uuid, params.get("metric"), params.get("group_by"), params.get("filter_dict")
                )
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "sql_join_aggregate":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_sql.run_join_aggregation,
                    params.get("left_dataset_uuid"), params.get("right_dataset_uuid"),
                    params.get("join_key"), params.get("metric"), params.get("group_by")
                )
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_rolling_average":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_pandas.calculate_rolling_average,
                    dataset_uuid, params.get("target_col"), params.get("window", 7), params.get("sort_col")
                )
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_correlation":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_pandas.calculate_correlation_matrix,
                    dataset_uuid, params.get("columns")
                )
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_outliers":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_pandas.detect_outliers,
                    dataset_uuid, params.get("target_col")
                )
                aggregator.add_structured_result(res)
                return res
                
            elif intent == "pandas_categorical_profiles":
                res = await wrap_engine_call(
                    intent, dataset_uuid, analytics_pandas.generate_categorical_profiles,
                    dataset_uuid
                )
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

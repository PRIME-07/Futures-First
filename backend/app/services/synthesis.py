import time
import json
from typing import Dict, Any, List
from openai import AsyncOpenAI
import os
import sys
from app.core.database import get_mongo_db
from app.core.config import settings

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("OpenAI API key not provided")
    sys.exit(1)

client = AsyncOpenAI(api_key=api_key)

async def resolve_original_filename(dataset_uuid: str) -> str:
    db = get_mongo_db()
    registry = await db.dataset_registry.find_one({"dataset_uuid": dataset_uuid})
    if registry:
        return registry.get("filename", dataset_uuid)
    return dataset_uuid

async def wrap_engine_call(tool_name: str, dataset_uuid: str, coroutine, *args, **kwargs) -> Dict[str, Any]:
    """
    Executes a tool, captures duration, row_count, previews, and resolves the dataset name.
    """
    start_time = time.time()
    status = "success"
    result_data = None
    error_msg = None
    
    try:
        result_data = await coroutine(*args, **kwargs)
    except Exception as e:
        status = "error"
        error_msg = str(e)
        
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Resolve filename
    original_filename = await resolve_original_filename(dataset_uuid) if dataset_uuid else "N/A"
    
    # Calculate row count and preview
    row_count = 0
    preview = ""
    if isinstance(result_data, list):
        row_count = len(result_data)
        preview = str(result_data[:2]) # Preview first 2 records
    elif isinstance(result_data, dict):
        if "outliers" in result_data:
            row_count = len(result_data["outliers"])
        else:
            row_count = len(result_data.keys())
        preview = str({k: result_data[k] for k in list(result_data.keys())[:2]})
    
    return {
        "tool_name": tool_name,
        "original_filename": original_filename,
        "duration_ms": duration_ms,
        "status": status,
        "row_count": row_count,
        "preview": preview,
        "data": result_data,
        "error": error_msg
    }

class MultiSourceAggregator:
    """
    Handles aggregation and conflict resolution across multiple analytical and retrieval engines.
    """
    def __init__(self):
        self.structured_results = []
        self.rag_contexts = []
        
    def add_structured_result(self, result: Dict[str, Any]):
        # Implementation of logical aggregation rules: SQL source of truth, Pandas for stats
        # For now, simply aggregates results to be passed to LLM synthesis.
        self.structured_results.append(result)
        
    def add_rag_contexts(self, contexts: List[Dict[str, Any]]):
        self.rag_contexts.extend(contexts)
        
    def get_aggregated_data(self) -> List[Dict[str, Any]]:
        return self.structured_results
        
    def get_rag_contexts(self) -> List[Dict[str, Any]]:
        return self.rag_contexts

async def generate_insight_summary(query: str, aggregated_data: List[Dict[str, Any]], rag_contexts: List[Dict[str, Any]]) -> str:
    """
    Calls gpt-5.4-mini to synthesize the final answer and recharts JSON.
    """
    system_prompt = """You are Insight Monkey, an expert data analyst and executive business intelligence officer.
You will be provided with a structured evidence bundle from SQL/Pandas analytics and unstructured RAG searches.
Your job is to answer the user's query using deeply structured analytical composition, derived KPIs, temporal reasoning, and grounded executive recommendations.

CRITICAL RULES:
1. EXECUTIVE COMMUNICATION TONE: Your tone must resemble a premium business intelligence report or executive strategy briefing. Sound analytical, concise, and insightful. Avoid robotic enumeration, generic consulting fluff, or mentioning internal system terms (e.g., 'sql_aggregate', 'JSON').
2. DERIVED KPI LAYER: You MUST compute deterministic business metrics (e.g., ROI, profit margin, revenue growth %, AOV, conversion lift, churn delta). Do not just restate raw numbers. (Example: "Revenue increased by 20% year-over-year..." instead of "Revenue went from 10M to 12M").
3. TEMPORAL REASONING LAYER: Explicitly compute temporal deltas. Perform before/after event analysis, compare pre/post averages, calculate growth %, and explicitly state trend acceleration or deceleration.
4. CROSS-SOURCE COMPARATIVE REASONING: You MUST explicitly align and compare structured metrics with RAG historical findings/benchmarks (e.g., "Current CTR trends (4.6%) remain broadly aligned with the historical 4.8% benchmark documented in the 2022 reports").
5. STATISTICAL INTERPRETATION & ALIGNMENT: Consistently use provided statistical interpretations (e.g., strong/moderate/weak correlation, direction, business interpretation). Explicitly state join metadata to validate alignment when merging tables.
6. STRICT DUAL-SOURCE CITATIONS: Always cite the structured data source (e.g., `[orders.csv]`) and unstructured data source/page (e.g., `[holiday_campaign.pdf, Page 2]`).
7. NO FACT FABRICATION: Only use the exact numbers and text provided. Ground all recommendations strictly in the provided evidence.

REQUIRED RESPONSE STRUCTURE:
You MUST format your analytical response into the following exact sections if applicable (skip sections if no data exists for them):
1. Executive Summary & KPIs
2. Quantitative Trends & Temporal Reasoning
3. Correlation Analysis & Join Metadata
4. Regional / Segment Insights
5. RAG Context & Cross-Source Comparison
6. Strategic Implications
7. Operational Recommendations
8. Confidence & Limitations

RECHARTS CONFIGURATION: If the user query benefits from a chart, include a JSON block enclosed in ```json ... ``` that contains a valid Recharts-compatible array. Keys MUST EXACTLY MATCH the lowercase, snake_case column names from the structured data provided.
"""

    evidence_bundle = {
        "aggregations": [],
        "correlations": [],
        "outliers": [],
        "rag_findings": [],
        "limitations": []
    }
    
    for tool_res in aggregated_data:
        tool_name = tool_res['tool_name']
        data = tool_res.get('data')
        source = tool_res['original_filename']
        if tool_name in ["sql_aggregate", "sql_join_aggregate", "pandas_rolling_average", "pandas_categorical_profiles"]:
            evidence_bundle["aggregations"].append({"source": source, "data": data})
        elif tool_name in ["pandas_correlation", "pandas_cross_dataset_correlation"]:
            evidence_bundle["correlations"].append({"source": source, "data": data})
        elif tool_name == "pandas_outliers":
            evidence_bundle["outliers"].append({"source": source, "data": data})
        elif tool_res.get("status") == "error":
            evidence_bundle["limitations"].append({"source": source, "error": tool_res.get("error")})

    for rag_res in rag_contexts:
        evidence_bundle["rag_findings"].append({
            "source": f"{rag_res.get('filename', 'Unknown')} (Page {rag_res.get('page_num', 1)})",
            "text": rag_res.get('text', '')
        })

    context_str = f"--- STRUCTURED EVIDENCE BUNDLE ---\n{json.dumps(evidence_bundle, indent=2)}\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"User Query: {query}\n\n{context_str}"}
    ]

    return await client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=messages,
        stream=True,
    )

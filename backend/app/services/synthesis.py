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
        return registry.get("original_filename") or registry.get("dataset_name") or dataset_uuid
    return dataset_uuid

async def fetch_chat_history_with_token_limit(session_id: str, max_tokens: int = 500) -> List[Dict[str, str]]:
    if not session_id:
        return []
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

async def generate_insight_summary(query: str, aggregated_data: List[Dict[str, Any]], rag_contexts: List[Dict[str, Any]], chart_metadata: List[Dict[str, Any]] = None, session_id: str = None) -> str:
    """
    Calls gpt-5.4-mini to synthesize the final answer and recharts JSON.
    """
    system_prompt = """You are Insight Monkey, an expert business analyst, data strategist, and executive business intelligence officer. You are highly capable of finding hidden anomalies, logical inconsistencies, and deep strategic insights across any business domain.
You will be provided with a structured evidence bundle from SQL/Pandas analytics and unstructured RAG searches.
Your job is to answer the user's query using deeply structured analytical composition, derived KPIs, temporal reasoning, and grounded executive recommendations.

CRITICAL RULES:
1. EXECUTIVE COMMUNICATION TONE: Your tone must resemble a premium business intelligence report or executive strategy briefing. Sound analytical, concise, and insightful. Avoid robotic enumeration, generic consulting fluff, or mentioning internal system terms/tool references (e.g., 'sql_aggregate', 'pandas_outliers', 'joined_timeseries', 'inner join', 'post_join_rows', 'RAG', 'retrieval', 'vector database'). Focus strictly on synthesizing insights from the available data. If a specific dimension (such as region or channel) is not present in the structured data, simply discuss the insights at the overall portfolio level. Avoid making technical excuses or complaining about missing metrics, column limitations, or RAG results.
2. DERIVED KPI LAYER: You MUST compute deterministic business metrics (e.g., ROI, profit margin, revenue growth %, AOV, conversion lift, churn delta). Do not just restate raw numbers. (Example: "Revenue increased by 20% year-over-year..." instead of "Revenue went from 10M to 12M").
3. TEMPORAL REASONING LAYER: Explicitly compute temporal deltas. Perform before/after event analysis, compare pre/post averages, calculate growth %, and explicitly state trend acceleration or deceleration.
4. CROSS-SOURCE COMPARATIVE REASONING & DUAL-SOURCE RECONCILIATION: You MUST explicitly align and compare structured metrics with historical findings/benchmarks (e.g., "Current CTR trends (4.6%) remain broadly aligned with the historical 4.8% benchmark documented in the reports"). You must integrate qualitative insights from PDF documents (like latency buffering issues, loyalty program launches) directly with the quantitative metrics from CSV/database files.
5. STATISTICAL INTERPRETATION & NO TECH LEAKS: Consistently use provided statistical interpretations (e.g., strong/moderate/weak correlation, direction, business interpretation). Describe data alignment in clean business terms (e.g., "analyzed 60 monthly data points over a 5-year timeframe") rather than printing technical databases/join properties (such as "Join type: inner", "Post-join rows", "Join key").
6. STRICT DUAL-SOURCE CITATIONS: Always cite the structured data source (e.g., `[orders.csv]`, `[subscriptions.csv]`, or `[streaming_metrics.csv]`) and unstructured document/page source (e.g., `[holiday_campaign.pdf, Page 2]` or `[subscriber_retention_analysis.pdf, Page 1]`). Every significant claim should have clear citations from both types of sources if they are provided in the evidence bundle. Never mention UUIDs or internal file registries.
7. NO FACT FABRICATION: Only use the exact numbers and text provided. Ground all recommendations strictly in the provided evidence.
8. TARGET SEGMENT VALIDATION: Verify that all structured numbers represent the exact target segment queried. If the structured evidence contains mixed or overall numbers, explicitly call out that the metrics represent the broader segment and identify it as a limitation.
9. MATHEMATICAL PRECISION, LOGICAL COHERENCE, AND CONTRADITIONS:
   - Double-check all percentage changes and divisions before printing. Ensure calculations are exact.
   - Actively cross-check different columns/metrics for mathematical coherence and logical consistency. For example, if active subscribers collapse by 74.3% in a single month (e.g. from 33.34M to 8.56M), check if this aligns with the reported monthly churn rate (8.67%). If there is a massive mathematical discrepancy (e.g. 8.67% monthly churn should only reduce the base by 2.89M, not 24.78M), you MUST explicitly point out this logical contradiction as a reporting anomaly, definition shift, or data discontinuity. Do not ignore mathematical inconsistencies.
10. COHORT & GRANULAR OUTLIER DETECTION:
   - Do not just rely on overall averages. Look at granular breakdowns (such as specific segments, categories, regions, or cohorts) to find hidden anomalies and contrasting trends.
   - Look for specific anomalies like "zombie cohorts" (segments showing high retention/pricing status but declining or negative active usage/engagement), high-volume low-performance combinations, or regional deviations, and draw meaningful strategic conclusions from them.
11. CONSTRUCTIVE CONFOUNDING ANALYSIS: Proactively scan data for external variables (e.g., financing rate shocks, component supply constraints) that may affect the core metrics, and present them to avoid single-cause attribution errors.
12. NO PLACEHOLDERS OR EXCUSES FOR MISSING DATA: Do NOT print placeholder explanations or complain that certain analyses or data were not provided.

REQUIRED RESPONSE STRUCTURE:
- You are free to organize the response dynamically using standard professional headers (using `##` and `###` markdown syntax) that best suit the complexity and structure of your analysis. Do NOT stick to a rigid template or output placeholder subheadings.
- However, you MUST place a concise `## TL;DR` section at the very end of your response. The TL;DR should be a 2-3 sentence executive takeaway summarizing the final answer to the user's primary query, and it must explicitly reference the key accompanying chart using the **[Chart Title]** syntax.

CHART REFERENCES: The Chart Agent has already generated and persisted the following charts to accompany your response. You MUST reference each chart naturally and explicitly inside the relevant section of your response using the format: **[Chart Title]**. Do not invent chart titles — only reference those listed below."""


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
        elif tool_name in ["pandas_correlation", "pandas_cross_dataset_correlation", "pandas_multi_join"]:
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

    charts_str = ""
    if chart_metadata:
        charts_str = "\n--- GENERATED CHARTS (reference these by title in your response) ---\n"
        for cm in chart_metadata:
            charts_str += f"- [{cm['title']}] (type: {cm['chart_type']}, id: {cm['chart_id']})\n"
    else:
        charts_str = "\n--- GENERATED CHARTS ---\nNo charts were generated for this query.\n"

    history = await fetch_chat_history_with_token_limit(session_id, max_tokens=500)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": f"User Query: {query}\n\n{context_str}{charts_str}"})

    return await client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=messages,
        stream=True,
    )

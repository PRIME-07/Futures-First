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
    system_prompt = """You are Insight Monkey, an expert data analyst.
You will be provided with structured data from SQL/Pandas analytical tools and unstructured text from RAG searches.
Your job is to answer the user's query comprehensively and naturally.

CRITICAL RULES:
1. STRICT DUAL-SOURCE CITATIONS:
   - For structured data, you MUST explicitly cite the original filename provided in the tool results (e.g., `[marketing_spend.csv]`).
   - For unstructured data, you MUST cite both the document name and the page number provided in the RAG contexts (e.g., `[quarterly_content_strategy.pdf, Page 3]`).
2. EXECUTIVE COMMUNICATION: NEVER mention internal system terms like 'sql_aggregate', 'pandas_outliers', 'tool_name', 'JSON', 'tool calls', or 'null'. Present the findings directly as a business analyst talking to a client.
3. GRACEFUL FALLBACKS: If the exact data requested isn't available in the context, DO NOT straight up refuse or complain about tool failures. Instead, provide the closest relevant insights using the data that WAS successfully retrieved, and gently mention what specific business metric would be needed to complete the full analysis.
4. RECHARTS CONFIGURATION: If the user query can benefit from a chart, include a JSON block enclosed in ```json ... ``` that contains a valid Recharts-compatible array of objects. Keys MUST EXACTLY MATCH the lowercase, snake_case column names from the structured data provided.
5. NO FACT FABRICATION: Only use the exact numbers and text provided in the context.
"""

    context_str = "--- STRUCTURED TOOL RESULTS ---\n"
    for tool_res in aggregated_data:
        context_str += f"Tool: {tool_res['tool_name']}\nSource: {tool_res['original_filename']}\nData: {json.dumps(tool_res['data'])}\n\n"
        
    context_str += "--- RAG TEXT CONTEXTS ---\n"
    for rag_res in rag_contexts:
        context_str += f"Source: {rag_res.get('filename', 'Unknown')} (Page {rag_res.get('page_num', 1)})\nText: {rag_res.get('text', '')}\n\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"User Query: {query}\n\nContext Data:\n{context_str}"}
    ]

    return await client.chat.completions.create(
        model=settings.MODEL_NAME,
        messages=messages,
        stream=True,
    )

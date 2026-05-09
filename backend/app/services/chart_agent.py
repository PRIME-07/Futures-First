import json
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from openai import AsyncOpenAI
import os

from app.core.database import get_mongo_db
from app.core.config import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Representational Intelligence: Heuristic-based chart type selection

TEMPORAL_KEYS = {"month", "date", "year", "week", "quarter", "day", "timestamp", "period"}
CATEGORICAL_KEYS = {"category", "genre", "region", "channel", "platform", "segment",
                    "type", "status", "brand", "supplier", "country", "city", "source"}
PROPORTION_KEYS = {"share", "percentage", "pct", "ratio", "proportion", "rate"}


def _detect_chart_type(data: List[Dict], x_key: str, y_keys: List[str], tool_name: str) -> str:
    """Deterministically select the best chart type based on data shape and tool context."""
    if tool_name == "pandas_outliers":
        return "composed"

    if not data or not x_key:
        return "bar"

    x_lower = x_key.lower()

    # Temporal heuristic
    if any(t in x_lower for t in TEMPORAL_KEYS):
        if len(y_keys) > 1:
            return "composed"
        return "line"

    # Proportional / share heuristic
    if any(p in y_key.lower() for y_key in y_keys for p in PROPORTION_KEYS):
        return "pie"

    # Categorical comparison heuristic
    if any(c in x_lower for c in CATEGORICAL_KEYS):
        return "bar"

    return "bar"


def _find_x_key(sample_row: Dict) -> str:
    """Find the most likely X-axis key from a sample data row."""
    keys = list(sample_row.keys())

    # Prefer explicit temporal keys first
    for k in keys:
        if any(t in k.lower() for t in TEMPORAL_KEYS):
            return k

    # Prefer categorical-sounding keys second
    for k in keys:
        if any(c in k.lower() for c in CATEGORICAL_KEYS):
            return k

    # Fall back to the first non-numeric-looking key
    for k in keys:
        if isinstance(sample_row[k], str):
            return k

    return keys[0] if keys else "index"


def _find_y_keys(sample_row: Dict, x_key: str) -> List[str]:
    """Find numeric metric keys to plot as Y-axis series."""
    return [
        k for k, v in sample_row.items()
        if k != x_key
        and k not in ("lower_bound", "upper_bound", "is_outlier")
        and isinstance(v, (int, float))
    ]


SERIES_COLORS = [
    "#3B82F6", "#10B981", "#F59E0B", "#EF4444",
    "#8B5CF6", "#06B6D4", "#F97316", "#84CC16"
]


def _build_series(y_keys: List[str], chart_type: str) -> List[Dict]:
    """Build the series config array for Recharts."""
    series = []
    for i, y_key in enumerate(y_keys):
        color = SERIES_COLORS[i % len(SERIES_COLORS)]
        series.append({
            "y_key": y_key,
            "label": y_key.replace("_", " ").title(),
            "color": color,
            "type": "bar" if chart_type == "bar" else "line"
        })

    return series


def _build_outlier_series(target_col: str) -> List[Dict]:
    """Build a composed series config for IQR outlier charts."""
    return [
        {"y_key": target_col, "label": target_col.replace("_", " ").title(), "color": "#3B82F6", "type": "line"},
        {"y_key": "lower_bound", "label": "Lower Bound (IQR)", "color": "#EF4444", "type": "line", "strokeDasharray": "4 4"},
        {"y_key": "upper_bound", "label": "Upper Bound (IQR)", "color": "#EF4444", "type": "line", "strokeDasharray": "4 4"},
    ]


# LLM-based chart title generator (lightweight, fast call)

async def _generate_chart_title(query: str, x_key: str, y_keys: List[str], chart_type: str) -> str:
    """Ask the LLM to generate a concise, business-friendly chart title."""
    prompt = (
        f"Generate a concise, professional business intelligence chart title (max 8 words) for a {chart_type} chart "
        f"that plots '{', '.join(y_keys)}' against '{x_key}', in the context of the following user question: \"{query}\". "
        f"Output ONLY the title, nothing else."
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception as e:
        logger.warning(f"Chart title generation failed: {e}")
        return f"{', '.join(y_keys).title()} by {x_key.title()}"


# Chart config builders per tool type

def _build_chart_from_aggregation(tool_result: Dict, query: str) -> Dict | None:
    """Build a chart config from SQL aggregation or rolling average data."""
    data = tool_result.get("data")
    tool_name = tool_result.get("tool_name", "")

    if not data or not isinstance(data, list) or len(data) == 0:
        return None

    sample = data[0]
    x_key = _find_x_key(sample)
    y_keys = _find_y_keys(sample, x_key)

    if not y_keys:
        return None

    chart_type = _detect_chart_type(data, x_key, y_keys, tool_name)
    series = _build_series(y_keys, chart_type)

    return {
        "_x_key": x_key,
        "_y_keys": y_keys,
        "chart_type": chart_type,
        "config": {"x_key": x_key, "series": series},
        "data": data,
    }


def _build_chart_from_correlation(tool_result: Dict, query: str) -> Dict | None:
    """Build a composed dual-series chart from a cross-dataset correlation result."""
    data = tool_result.get("data")
    if not data or not isinstance(data, dict):
        return None

    inner_data = data.get("data")
    columns = data.get("columns", [])

    if not inner_data or not isinstance(inner_data, list) or len(columns) < 2:
        return None

    sample = inner_data[0]
    x_key = _find_x_key(sample)
    y_keys = [c for c in columns if c != x_key]

    series = _build_series(y_keys, "composed")
    return {
        "_x_key": x_key,
        "_y_keys": y_keys,
        "chart_type": "composed",
        "config": {"x_key": x_key, "series": series},
        "data": inner_data,
    }


def _build_chart_from_outliers(tool_result: Dict, query: str) -> Dict | None:
    """Build a composed IQR boundary chart from outlier detection results."""
    data = tool_result.get("data")
    if not data or not isinstance(data, dict):
        return None

    chart_data = data.get("chart_data")
    target_col = data.get("metric")

    if not chart_data or not target_col:
        return None

    # Detect the best x_key from the chart data (temporal if available)
    sample = chart_data[0] if chart_data else {}
    x_key = _find_x_key(sample)

    # Remove non-plottable keys from x_key candidates
    if x_key in ("lower_bound", "upper_bound", "is_outlier"):
        x_key = target_col

    series = _build_outlier_series(target_col)
    return {
        "_x_key": x_key,
        "_y_keys": [target_col],
        "chart_type": "composed",
        "config": {"x_key": x_key, "series": series},
        "data": chart_data,
    }


def _build_chart_from_categorical(tool_result: Dict, query: str) -> List[Dict] | None:
    """Build bar charts from categorical profile data (one per detected category)."""
    data = tool_result.get("data")
    if not data or not isinstance(data, dict):
        return None

    profiles = data.get("profiles", {})
    if not profiles:
        return None

    charts = []
    for cat_col, cat_data in profiles.items():
        rows = []
        y_keys_set = set()
        for segment_name, stats in cat_data.items():
            row = {cat_col: segment_name}
            for k, v in stats.items():
                if k != "record_count" and isinstance(v, (int, float)):
                    row[k] = v
                    y_keys_set.add(k)
            rows.append(row)

        if not rows or not y_keys_set:
            continue

        y_keys = list(y_keys_set)[:3]  # Limit to 3 series for readability
        series = _build_series(y_keys, "bar")
        charts.append({
            "_x_key": cat_col,
            "_y_keys": y_keys,
            "chart_type": "bar",
            "config": {"x_key": cat_col, "series": series},
            "data": rows,
        })

    return charts if charts else None


# Main Chart Agent entry point

async def run_chart_agent(
    query: str,
    session_id: str,
    aggregated_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Core Chart Agent.

    Receives the Evidence Bundle from the orchestrator, applies representational
    intelligence heuristics, generates chart configs with LLM-produced titles,
    persists each chart document to MongoDB, and returns lightweight metadata
    for the Synthesizer to reference.

    Returns a list of chart metadata dicts:
    [{"chart_id": "...", "title": "...", "chart_type": "..."}]
    """
    if not aggregated_data:
        logger.info("Chart Agent: No analytical data in evidence bundle. Skipping chart generation.")
        return []

    raw_charts: List[Dict] = []

    for tool_result in aggregated_data:
        if tool_result.get("status") == "error":
            continue

        tool_name = tool_result.get("tool_name", "")

        if tool_name in ("sql_aggregate", "sql_join_aggregate", "pandas_rolling_average"):
            chart = _build_chart_from_aggregation(tool_result, query)
            if chart:
                raw_charts.append(chart)

        elif tool_name in ("pandas_correlation", "pandas_cross_dataset_correlation"):
            chart = _build_chart_from_correlation(tool_result, query)
            if chart:
                raw_charts.append(chart)

        elif tool_name == "pandas_outliers":
            chart = _build_chart_from_outliers(tool_result, query)
            if chart:
                raw_charts.append(chart)

        elif tool_name == "pandas_categorical_profiles":
            charts = _build_chart_from_categorical(tool_result, query)
            if charts:
                raw_charts.extend(charts)

    if not raw_charts:
        logger.info("Chart Agent: No plottable data found in evidence bundle.")
        return []

    # Generate titles and persist to MongoDB
    db = get_mongo_db()
    chart_metadata = []

    for raw in raw_charts:
        x_key = raw.pop("_x_key")
        y_keys = raw.pop("_y_keys")

        title = await _generate_chart_title(query, x_key, y_keys, raw["chart_type"])
        chart_id = str(uuid.uuid4())

        chart_doc = {
            "_id": chart_id,
            "session_id": session_id,
            "title": title,
            "chart_type": raw["chart_type"],
            "config": raw["config"],
            "data": raw["data"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await db.charts.insert_one(chart_doc)
            logger.info(f"Chart Agent: Persisted chart '{title}' [{chart_id}]")
        except Exception as e:
            logger.error(f"Chart Agent: Failed to persist chart: {e}")
            continue

        chart_metadata.append({
            "chart_id": chart_id,
            "title": title,
            "chart_type": raw["chart_type"],
        })

    return chart_metadata

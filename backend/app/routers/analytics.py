from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from app.services import analytics_sql, analytics_pandas

router = APIRouter(prefix="/analytics", tags=["analytics"])

class AggregationRequest(BaseModel):
    dataset_uuid: str
    metric: str
    group_by: str
    filter_dict: Optional[Dict] = None

class JoinAggregationRequest(BaseModel):
    left_dataset_uuid: str
    right_dataset_uuid: str
    join_key: str
    metric: str
    group_by: str

class RollingAvgRequest(BaseModel):
    dataset_uuid: str
    target_col: str
    window: int
    sort_col: Optional[str] = None

class CorrelationRequest(BaseModel):
    dataset_uuid: str
    columns: Optional[List[str]] = None

class OutlierRequest(BaseModel):
    dataset_uuid: str
    target_col: str

class CategoricalProfilesRequest(BaseModel):
    dataset_uuid: str

class CrossDatasetCorrelationRequest(BaseModel):
    dataset1_uuid: str
    metric1: str
    dataset2_uuid: str
    metric2: str
    join_key: str
    filter_dict1: Optional[Dict] = None
    filter_dict2: Optional[Dict] = None

@router.post("/sql/aggregate")
async def sql_aggregate(req: AggregationRequest):
    try:
        res = await analytics_sql.run_aggregation(req.dataset_uuid, req.metric, req.group_by, req.filter_dict)
        return {"status": "success", "data": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sql/join_aggregate")
async def sql_join_aggregate(req: JoinAggregationRequest):
    try:
        res = await analytics_sql.run_join_aggregation(req.left_dataset_uuid, req.right_dataset_uuid, req.join_key, req.metric, req.group_by)
        return {"status": "success", "data": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pandas/rolling_average")
async def pandas_rolling_avg(req: RollingAvgRequest):
    try:
        res = await analytics_pandas.calculate_rolling_average(req.dataset_uuid, req.target_col, req.window, req.sort_col)
        return {"status": "success", "data": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pandas/correlation")
async def pandas_correlation(req: CorrelationRequest):
    try:
        res = await analytics_pandas.calculate_correlation_matrix(req.dataset_uuid, req.columns)
        return {"status": "success", "data": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pandas/cross_dataset_correlation")
async def pandas_cross_dataset_correlation(req: CrossDatasetCorrelationRequest):
    try:
        res = await analytics_pandas.cross_dataset_correlation(
            req.dataset1_uuid, req.metric1, req.dataset2_uuid, req.metric2, req.join_key,
            req.filter_dict1, req.filter_dict2
        )
        return {"status": "success", "data": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pandas/outliers")
async def pandas_outliers(req: OutlierRequest):
    try:
        res = await analytics_pandas.detect_outliers(req.dataset_uuid, req.target_col)
        return {"status": "success", "data": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/pandas/categorical_profiles")
async def pandas_categorical_profiles(req: CategoricalProfilesRequest):
    try:
         res = await analytics_pandas.generate_categorical_profiles(req.dataset_uuid)
         return {"status": "success", "data": res}
    except ValueError as e:
         raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/charts")
async def get_session_charts(session_id: str):
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()
        cursor = db.charts.find({"session_id": session_id})
        charts = await cursor.to_list(length=100)
        return {"status": "success", "data": charts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch session charts: {str(e)}")

@router.get("/charts/{chart_id}")
async def get_chart_details(chart_id: str):
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()
        chart = await db.charts.find_one({"_id": chart_id})
        if not chart:
            raise HTTPException(status_code=404, detail="Chart not found")
        return {"status": "success", "data": chart}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch chart details: {str(e)}")

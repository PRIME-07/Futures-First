from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio
import logging
from pydantic import BaseModel
from app.services.synthesis import MultiSourceAggregator, generate_insight_summary
from app.services.orchestrator import orchestrate_pipeline
from app.services.chart_agent import run_chart_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stream", tags=["stream"])

class StreamRequest(BaseModel):
    session_id: str
    query: str

async def sse_generator(req: StreamRequest):
    queue = asyncio.Queue()
    
    async def run_pipeline():
        try:
            # 1. Pipeline Start
            await queue.put(f"event: pipeline_start\ndata: {json.dumps({'message': 'Starting analysis pipeline...'})}\n\n")
            await asyncio.sleep(0.5)
            
            aggregator = MultiSourceAggregator()
            
            # 2. Execute Orchestration (Classification -> Variable Extraction -> Tool Execution)
            await queue.put(f"event: orchestration_start\ndata: {json.dumps({'message': 'Analyzing query and routing to tools...'})}\n\n")
            
            async def on_retry(attempt, max_retries, error_type):
                msg = f"Model generated an incorrect output format. Retrying... (Attempt {attempt}/{max_retries})"
                await queue.put(f"event: orchestration_retry\ndata: {json.dumps({'message': msg, 'attempt': attempt, 'max_retries': max_retries})}\n\n")
            
            telemetries = await orchestrate_pipeline(req.query, req.session_id, aggregator, on_retry=on_retry)
            
            # 3. Yield Tool Telemetry
            if telemetries:
                for t in telemetries:
                    if t:
                        await queue.put(f"event: tool_complete\ndata: {json.dumps(t)}\n\n")

            # 4. Chart Agent (middle layer between Orchestrator and Synthesizer)
            await queue.put(f"event: chart_agent_start\ndata: {json.dumps({'message': 'Generating visual chart configurations...'})}\n\n")
            chart_metadata = await run_chart_agent(req.query, req.session_id, aggregator.get_aggregated_data())

            if chart_metadata:
                for cm in chart_metadata:
                    await queue.put(f"event: chart_generated\ndata: {json.dumps(cm)}\n\n")
            else:
                logger.info("Graphs not available for this query.")
                await queue.put(f"event: chart_telemetry\ndata: {json.dumps({'message': 'Graphs not available for this query.'})}\n\n")

            # 5. Synthesis
            await queue.put(f"event: synthesis_start\ndata: {json.dumps({'message': 'Synthesizing final insights...'})}\n\n")
            
            response_stream = await generate_insight_summary(
                req.query, 
                aggregator.get_aggregated_data(), 
                aggregator.get_rag_contexts(),
                chart_metadata
            )
            
            full_answer = ""
            async for chunk in response_stream:
                content = chunk.choices[0].delta.content if chunk.choices and chunk.choices[0].delta.content else ""
                if content:
                    full_answer += content
                    await queue.put(f"event: token\ndata: {json.dumps({'token': content})}\n\n")
                    
            response_payload = {
                "answer": full_answer
            }
            await queue.put(f"event: response_complete\ndata: {json.dumps(response_payload)}\n\n")
        except Exception as e:
            await queue.put(f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n")
        finally:
            await queue.put(None)
            
    # Run the pipeline completely in the background so we can yield instantly!
    asyncio.create_task(run_pipeline())
    
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item

@router.post("/")
async def stream_analysis(req: StreamRequest):
    return StreamingResponse(sse_generator(req), media_type="text/event-stream")

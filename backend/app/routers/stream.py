from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio
import logging
from pydantic import BaseModel
from app.services.synthesis import MultiSourceAggregator, generate_insight_summary
from app.services.orchestrator import orchestrate_pipeline, client, settings
from app.services.chart_agent import run_chart_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stream", tags=["stream"])

class StreamRequest(BaseModel):
    session_id: str
    query: str

def is_casual_query(query: str) -> bool:
    q = query.strip().lower().rstrip("?").rstrip("!").rstrip(".")
    casual_words = {
        "hi", "hello", "hey", "hola", "yo", "greetings", "good morning", "good afternoon", "good evening", 
        "how are you", "who are you", "what are you", "what can you do", "how can you help", "help", 
        "tell me about yourself", "how do you work", "how to use", "how can i help you", "whats up", "what's up",
        "hey there", "hello there"
    }
    if q in casual_words:
        return True
    words = q.split()
    if len(words) <= 3 and any(w in ["hi", "hello", "hey", "help", "greet", "greetings"] for w in words):
        return True
    return False

async def is_conversational_query(query: str) -> bool:
    try:
        system_prompt = (
            "You are an intent classifier. Categorize the user's input into one of two categories:\n"
            "- 'conversational': If the user is greeting you, asking how you are, asking what you are, asking about your capabilities, "
            "asking what data you can see/access, asking for help on how to use the app, making general chitchat, "
            "or asking off-topic requests (like writing poems, stories, code/programming questions, essays, recipes, etc.).\n"
            "- 'analytical': If the user is asking for specific analysis, calculations, trends, metrics, correlations, outliers, or questions "
            "about their business data (e.g. sales, churn, pricing, performance, marketing spend, EV sales, etc.).\n"
            "Respond with a JSON object containing exactly one key 'category' with the value 'conversational' or 'analytical'."
        )
        response = await client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("category") == "conversational"
    except Exception as e:
        logger.error(f"Error in is_conversational_query classifier: {e}")
        return is_casual_query(query)

async def sse_generator(req: StreamRequest):
    queue = asyncio.Queue()
    
    async def run_pipeline():
        try:
            if await is_conversational_query(req.query):
                await queue.put(f"event: pipeline_start\ndata: {json.dumps({'message': 'Analyzing request...'})}\n\n")
                await queue.put(f"event: synthesis_start\ndata: {json.dumps({'message': 'Formulating friendly response...'})}\n\n")
                
                system_prompt = """You are Insight Monkey, a highly skilled executive data analyst and business intelligence assistant.
Since the user is greeting you, asking about your capabilities, or asking general chitchat (rather than requesting specific data calculations), respond warmly and elegantly.
Always be warm, welcoming, and explicitly introduce yourself in the first sentence (e.g., if the user says 'hi', start with 'Hi! I'm Insight Monkey, your dedicated AI business intelligence assistant. I can help you...').

OFF-TOPIC POLICY:
If the user's input asks you to write creative fiction (stories, poems, jokes), essays, code/programming files, recipes, or perform any task unrelated to business intelligence and data analytics, you MUST kindly and politely refuse to answer. Explain that your capabilities are strictly focused on business data analytics, statistical modeling, RAG document search, and interactive visualizations. Do not fulfill off-topic requests under any circumstances.

Briefly explain how you can help them:
- They can upload CSV/Excel business datasets or PDF reports.
- They can ask you to correlate metrics, calculate rolling averages, detect outliers, perform categorical profiling, or run complex SQL/Pandas analytical summaries.
- You can generate dynamic, beautiful interactive charts (Composed, Bar, Line, Area, Scatter, etc.) and perform transient PDF RAG citation searches.
- If they ask what data you can access or see, explain that you have full access to all the active data sources and connections loaded into the session, which are listed and visible in the right sidebar panel.
Keep your response warm, friendly, executive, and under 3 paragraphs."""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": req.query}
                ]
                
                response_stream = await client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    messages=messages,
                    stream=True,
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
                
                # Persist chat history to MongoDB
                try:
                    from app.core.database import get_mongo_db
                    from datetime import datetime
                    db = get_mongo_db()
                    await db.chats.insert_one({
                        "session_id": req.session_id,
                        "query": req.query,
                        "answer": full_answer,
                        "timestamp": datetime.now()
                    })
                except Exception as mongo_err:
                    logger.error(f"Failed to save chat to MongoDB: {mongo_err}")
                return

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
                chart_metadata,
                session_id=req.session_id
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

            # Persist chat history to MongoDB
            try:
                from app.core.database import get_mongo_db
                from datetime import datetime
                db = get_mongo_db()
                await db.chats.insert_one({
                    "session_id": req.session_id,
                    "query": req.query,
                    "answer": full_answer,
                    "timestamp": datetime.now()
                })
            except Exception as mongo_err:
                logger.error(f"Failed to save chat to MongoDB: {mongo_err}")

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

@router.get("/sessions/{session_id}/chats")
async def list_session_chats(session_id: str):
    """Retrieve chronologically ordered chat history for a session."""
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()
        
        chats = []
        cursor = db.chats.find({"session_id": session_id}).sort("timestamp", 1)
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if "timestamp" in doc and doc["timestamp"]:
                doc["timestamp"] = doc["timestamp"].isoformat()
            chats.append(doc)
            
        return {"status": "success", "data": chats}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat history: {str(e)}")

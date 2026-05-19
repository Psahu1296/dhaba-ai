from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tools.bill_app import login, get_top_dishes, get_dashboard_kpis
from fastapi.responses import StreamingResponse
from agent import run_agent, run_agent_stream
from config import API_KEY
from graph import run_graph, run_graph_stream
import uuid
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from tools.daily_embedder import embed_day



@asynccontextmanager
async def lifespan(app: FastAPI):
    await login()
    print("✓ Logged into Bill-App")

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(embed_day, CronTrigger(hour=0, minute=30))
    scheduler.start()
    print("✓ Daily embedder scheduled at 00:30 IST")

    yield

    scheduler.shutdown()


app = FastAPI(title="Dhaba AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# Define the header name the client must send
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key

# Pydantic model = shape of the request body
# JS equivalent: type ChatRequest = { message: string }
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

@app.get("/")
async def root():
    return {"status": "Dhaba AI running"}

@app.post("/admin/embed-day")
async def trigger_embed(date: str = None):
    await embed_day(date)
    return {"status": "embedded", "date": date or "yesterday"}


@app.get("/dishes/top")
async def top_dishes(limit: int = 5):
    return await get_top_dishes(limit)


@app.get("/kpis")
async def kpis():
    return await get_dashboard_kpis()


@app.post("/chat", dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    answer = await run_agent(req.message)
    return {"answer": answer}


@app.post("/chat/stream", dependencies=[Depends(require_api_key)])
async def chat_stream_endpoint(req: ChatRequest):
    async def generate():
        async for token in run_agent_stream(req.message):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/agent/chat", dependencies=[Depends(require_api_key)])
async def agent_chat(req: ChatRequest):
    thread_id = req.session_id or str(uuid.uuid4())
    answer = await run_graph(req.message, thread_id)
    return {"answer": answer, "session_id": thread_id}

@app.post("/agent/chat/stream", dependencies=[Depends(require_api_key)])
async def agent_chat_stream(req: ChatRequest):
    thread_id = req.session_id or str(uuid.uuid4())
    async def generate():
        async for token in run_graph_stream(req.message, thread_id):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")
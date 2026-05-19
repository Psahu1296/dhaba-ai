import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional
import uuid

from config import API_KEY
from tools.bill_app import login, get_top_dishes, get_dashboard_kpis
from tools.daily_embedder import embed_day
from tools.embedder import embed_menu
from agent import run_agent, run_agent_stream
from graph import run_graph, run_graph_stream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await login()
    logger.info("Logged into Bill-App")

    async def _bg_embed():
        try:
            await embed_menu()
        except Exception as e:
            logger.warning(f"Menu embedding skipped: {e}")

    asyncio.create_task(_bg_embed())

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(embed_day, CronTrigger(hour=0, minute=30))
    scheduler.start()
    logger.info("Daily embedder scheduled at 00:30 IST")

    yield

    scheduler.shutdown()


app = FastAPI(title="Dhaba AI", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@app.get("/")
async def root():
    return {"status": "Dhaba AI running"}


@app.post("/admin/embed-day", dependencies=[Depends(require_api_key)])
async def trigger_embed(date: str = None):
    await embed_day(date)
    logger.info(f"Manual embed triggered for date: {date or 'yesterday'}")
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
@limiter.limit("30/minute")
async def agent_chat_stream(request: Request, req: ChatRequest):
    thread_id = req.session_id or str(uuid.uuid4())
    async def generate():
        async for token in run_graph_stream(req.message, thread_id):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")

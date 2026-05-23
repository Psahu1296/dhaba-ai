import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional
import uuid
import jwt as pyjwt
import httpx

from config import API_KEY, DATABASE_URL, JWT_SECRET, BILL_APP_URL
from tools.bill_app import login as bill_app_login, get_top_dishes, get_dashboard_kpis
from tools.daily_embedder import embed_day
from tools.embedder import embed_menu
from tools import codec
from agent import run_agent, run_agent_stream
from graph import run_graph, run_graph_stream, init_graph
from pipeline.graph import init_pipeline, run_pipeline, run_pipeline_stream
from db import init_db
from reports import generate_daily_report


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(DATABASE_URL)
    await init_graph(DATABASE_URL)
    await init_pipeline(DATABASE_URL)
    async def _bg_startup():
        try:
            await bill_app_login()
            logger.info("Logged into Bill-App")
        except Exception as e:
            logger.warning(f"Bill-App login failed: {e}")
        try:
            await embed_menu()
        except Exception as e:
            logger.warning(f"Menu embedding skipped: {e}")

    asyncio.create_task(_bg_startup())

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(embed_day, CronTrigger(hour=0, minute=30, timezone="Asia/Kolkata"))
    scheduler.add_job(generate_daily_report, CronTrigger(hour=23, minute=0, timezone="Asia/Kolkata"))
    scheduler.start()
    logger.info("Scheduler started: embedder at 00:30 IST, report at 23:00 IST")

    yield

    scheduler.shutdown()


app = FastAPI(title="Dhaba AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def require_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


async def get_current_user(
    key: str = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> dict:
    if key and key == API_KEY:
        return {"role": "admin", "name": "API User"}
    if bearer:
        try:
            payload = pyjwt.decode(bearer.credentials, JWT_SECRET, algorithms=["HS256"])
            return {"role": payload.get("role", "staff"), "name": payload.get("name", "")}
        except pyjwt.PyJWTError:
            pass
    raise HTTPException(status_code=401, detail="Invalid or missing auth")


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class FeedbackRequest(BaseModel):
    session_id: str
    query: str
    response: str
    rating: int               # 1 = good, -1 = bad
    source: str = "explicit"  # "explicit" | "implicit"
    correction: Optional[str] = None


@app.get("/")
async def root():
    return {"status": "Dhaba AI running"}


@app.post("/login")
async def login(req: LoginRequest):
    async with httpx.AsyncClient(base_url=BILL_APP_URL, timeout=10) as client:
        r = await client.post("/api/user/login", json={"email": req.email, "password": req.password})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        cookie = r.cookies.get("accessToken")
        if not cookie:
            raise HTTPException(status_code=401, detail="Bill-App did not return a session")
        r2 = await client.get("/api/user", cookies={"accessToken": cookie})
        if r2.status_code != 200:
            raise HTTPException(status_code=401, detail="Could not fetch user profile")
        user = r2.json()["data"]

    token = pyjwt.encode(
        {"email": user["email"], "name": user["name"], "role": user["role"]},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"token": token, "role": user["role"], "name": user["name"]}


@app.post("/feedback", dependencies=[Depends(get_current_user)])
async def submit_feedback(req: FeedbackRequest):
    from db import save_feedback
    await save_feedback(req.session_id, req.query, req.response, req.rating, req.source, req.correction)
    return {"status": "saved"}


@app.get("/admin/feedback/stats", dependencies=[Depends(require_api_key)])
async def feedback_stats():
    from db import get_feedback_stats
    return await get_feedback_stats()


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


@app.post("/chat", dependencies=[Depends(get_current_user)])
async def chat(req: ChatRequest):
    answer = await run_agent(req.message)
    return {"answer": answer, "toon_chars_saved": codec.total_chars_saved()}


@app.post("/chat/stream", dependencies=[Depends(get_current_user)])
async def chat_stream_endpoint(req: ChatRequest):
    async def generate():
        async for token in run_agent_stream(req.message):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/agent/chat")
async def agent_chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    thread_id = req.session_id or str(uuid.uuid4())
    answer = await run_pipeline(req.message, thread_id, role=user["role"])
    return {"answer": answer, "session_id": thread_id, "toon_chars_saved": codec.total_chars_saved()}


@app.post("/agent/chat/stream")
async def agent_chat_stream(req: ChatRequest, user: dict = Depends(get_current_user)):
    thread_id = req.session_id or str(uuid.uuid4())
    async def generate():
        async for token in run_pipeline_stream(req.message, thread_id, role=user["role"]):
            yield token
    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/report/latest")
async def get_report():
    from db import get_latest_report
    report = await get_latest_report()
    if not report:
        return {"report": None, "message": "No report generated yet"}
    return {"report_date": report.report_date, "content": report.content, "generated_at": report.generated_at}


@app.post("/admin/report/generate", dependencies=[Depends(require_api_key)])
async def trigger_report(date: str = None):
    content = await generate_daily_report(date)
    return {"status": "generated", "date": date or "today", "length": len(content)}

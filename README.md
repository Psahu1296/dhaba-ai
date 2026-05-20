# Dhaba AI

AI-powered business intelligence layer on top of a real production dhaba (Indian restaurant) POS system. Built as a portfolio project demonstrating RAG, tool calling, LangGraph agents, persistent memory, and streaming — all on live data.

**Live demo:** [dhaba-ai-production.up.railway.app](https://dhaba-ai-production.up.railway.app)

---

## What it does

The owner can ask natural language questions about their business and get accurate, data-backed answers in real time:

- *"What item sold most today?"*
- *"Who owes us money?"*
- *"Show me revenue trend for the last 7 days"*
- *"What time did we get the most orders yesterday?"*
- *"How much chai was sold this week?"*
- *"Which day had the best revenue this month?"*

---

## Architecture

```
React Frontend (Vite + Tailwind)
        │
        │  POST /agent/chat/stream   (X-API-Key auth)
        ▼
FastAPI Backend (Railway)
        │
        ▼
LangGraph ReAct Agent
  ├── Tool Node ──► Bill-App Express API (live POS data, port 5005)
  ├── LLM Node  ──► Ollama (local) / OpenAI-compatible
  └── Checkpointer ──► PostgreSQL (conversation memory per session)
        │
        └── ChromaDB (dish embeddings + daily summary embeddings)

APScheduler
  ├── 00:30 IST ──► embed_day()         (nightly summary embeddings)
  └── 23:00 IST ──► generate_daily_report()  (LangGraph → Postgres)
```

**Data flow:** User asks → LangGraph agent picks tools → calls live Bill-App API → LLM synthesizes → streams back token by token. Conversation state persists in Postgres across sessions and restarts.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind v4 |
| Backend | FastAPI, Python 3.11 |
| Agent | LangGraph (ReAct loop), LangChain |
| LLM | Ollama (qwen3.5:4b, local) / OpenAI-compatible |
| Memory | PostgreSQL via AsyncPostgresSaver (persistent) |
| Vector DB | ChromaDB (persistent, dish + daily embeddings) |
| Embeddings | nomic-embed-text via Ollama |
| Scheduler | APScheduler (nightly embed + report generation) |
| Tracing | LangSmith |
| Deployment | Railway (backend + Postgres) |
| POS System | Bill-App (Electron + Express + SQLite) |

---

## Features

### Two chat modes
- **Stream mode** — fast, stateless, streams tokens live. Good for quick menu queries.
- **Agent mode** — LangGraph multi-step ReAct loop. Persistent conversation memory via PostgreSQL. Calls multiple tools, reasons across results.

### 14 tools wired to live POS API

| Tool | What it returns |
|---|---|
| `get_dashboard_kpis` | Today's revenue, order count, % change vs yesterday |
| `get_revenue` | Earnings for day / week / month / year |
| `get_earnings_history` | Time-series for trend analysis — best/worst period pre-identified |
| `get_todays_top_items` | Items sold most on any given date (aggregated in Python) |
| `get_peak_hours_today` | Busiest order hours on any given date |
| `get_top_dishes` | All-time bestsellers (historical, not today) |
| `get_orders` | Order list with date and status filters |
| `get_expenses` | Expense records with date range filter |
| `get_customer_balance` | Outstanding balance for one customer (by phone) |
| `get_all_customer_ledgers` | All customer dues, sorted by balance descending |
| `get_consumables_summary` | Tea / gutka / cigarette usage breakdown |
| `get_all_dishes` | Full menu with optional veg/non-veg and price filters |
| `search_dishes` | Semantic search over menu (RAG) |
| `search_daily_history` | Semantic search over historical daily summaries (RAG) |

### Persistent conversation memory
Each chat session gets a `session_id`. LangGraph checkpoints the full conversation state (messages, tool calls, reasoning steps) to PostgreSQL via `AsyncPostgresSaver`. Sessions survive server restarts and Railway redeploys. The frontend persists `session_id` in `localStorage` — refresh the page and the agent remembers the full context.

### RAG pipeline
- Menu dishes embedded with `nomic-embed-text` into ChromaDB at startup
- Daily summaries (revenue, top items, peak hours) auto-embedded nightly at 00:30 IST
- Enables historical trend queries ("which week was slowest last month") without scanning raw order records

### TOON compression
Tool results are encoded in TOON format — a compact LLM-readable notation that reduces token count by ~88% on array-heavy payloads (order lists, ledger records). Each response includes `toon_chars_saved` showing the compression applied. Green badge visible in the UI.

### Daily business report
Every night at 23:00 IST, APScheduler triggers the LangGraph agent with a fixed prompt that calls 4 tools (KPIs, top items, expenses, peak hours) and generates a structured report. Stored in a `daily_reports` Postgres table. Accessible via `/report/latest` or the **Report** button in the frontend header — instant load, no LLM call at read time.

### Evals
20 Q&A pairs tested against live production data.

```
Score: 5.0 / 5.0  ✅  (20/20 questions)
```

Run yourself:
```bash
python3 evals/run_remote.py   # hits Railway API, no local dependencies
python3 evals/score.py        # keyword-based scorer, instant
```

---

## Project structure

```
dhaba-ai/
├── main.py              # FastAPI app, routes, auth middleware, APScheduler
├── graph.py             # LangGraph ReAct agent (AsyncPostgresSaver)
├── agent.py             # Simple streaming agent (/chat/stream)
├── reports.py           # Daily report generator (LangGraph + Postgres)
├── db.py                # SQLAlchemy models (ChatLog, DailyReport) + init
├── llm.py               # LLM client (OpenAI SDK → Ollama)
├── config.py            # Env var loading
├── requirements.txt
├── Dockerfile
├── railway.toml
├── tools/
│   ├── bill_app.py      # Bill-App API calls (httpx, cookie auth, aggregation)
│   ├── lc_tools.py      # LangChain @tool wrappers + ALL_TOOLS list
│   ├── definitions.py   # OpenAI tool schemas (legacy agent)
│   ├── embedder.py      # One-time dish menu embedder
│   ├── daily_embedder.py# Nightly summary embedder + ChromaDB search
│   ├── retriever.py     # Dish semantic search
│   └── codec.py         # TOON encoder/decoder
├── toon_format/         # TOON compression library
├── evals/
│   ├── questions.json   # 20 test questions with expected topics
│   ├── run.py           # Local eval runner
│   ├── run_remote.py    # Remote eval runner (hits Railway, no local deps)
│   ├── score.py         # Keyword-based scorer
│   └── results.json     # Latest eval results
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── hooks/useChat.ts   # Session management, streaming, report fetch
    │   ├── components/
    │   │   ├── MessageBubble.tsx
    │   │   └── InputBar.tsx
    │   └── types.ts
    └── package.json
```

---

## API endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | — | Health check |
| POST | `/agent/chat` | ✅ | LangGraph agent, full JSON response |
| POST | `/agent/chat/stream` | ✅ | LangGraph agent, token stream |
| POST | `/chat` | ✅ | Simple agent, full JSON |
| POST | `/chat/stream` | ✅ | Simple agent, token stream |
| GET | `/report/latest` | — | Latest daily report from Postgres |
| GET | `/dishes/top` | — | Top dishes passthrough |
| GET | `/kpis` | — | KPIs passthrough |
| POST | `/admin/report/generate` | ✅ | Manually trigger report generation |
| POST | `/admin/embed-day` | ✅ | Manually trigger daily embedding |

Auth = `X-API-Key` header required.

---

## Running locally

### Prerequisites
- [Ollama](https://ollama.ai) running with `qwen3.5:4b` and `nomic-embed-text`
- Bill-App backend running on port 5005
- PostgreSQL (or use Railway Postgres with `DATABASE_URL`)
- Python 3.11+, Node 18+

### Backend

```bash
git clone https://github.com/Psahu1296/dhaba-ai
cd dhaba-ai

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # fill in your values

# seed dish embeddings (one time)
python3 -m tools.embedder

uvicorn main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # set VITE_API_BASE and VITE_API_KEY
npm run dev
```

### Environment variables

```env
BILL_APP_URL=http://localhost:5005
BILL_APP_EMAIL=your_email
BILL_APP_PASSWORD=your_password
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3.5:4b
API_KEY=your_secret_key
DATABASE_URL=postgresql://user:pass@host:port/dbname
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=dhaba-ai
```

---

## Key design decisions

**Postgres over in-memory checkpointing** — `MemorySaver` loses all conversation state on restart. `AsyncPostgresSaver` stores LangGraph's full checkpoint (messages, tool call history, node state) in Postgres. The frontend persists `session_id` in `localStorage`, so users get true multi-session continuity.

**Pre-aggregate in Python, not the LLM** — `get_todays_top_items` and `get_peak_hours_today` parse and aggregate raw order JSON in Python before returning to the LLM. LLMs reliably fail when asked to count or group from nested raw JSON at scale.

**RAG + tools, not one or the other** — Tools for real-time queries (today's revenue, live orders). RAG for semantic search over static data (menu) and historical patterns (trend queries spanning many days of summaries).

**Pre-generated daily reports** — The report at `/report/latest` is generated by the agent at 23:00 IST and stored. Reading it costs zero tokens and responds instantly — versus re-running 4 tool calls on every page load.

**TOON compression** — Tool results arrive as large JSON arrays. TOON encodes them into a compact tabular format the LLM reads natively, reducing token usage ~88% on array payloads. Keeps costs low with OpenAI and speeds up local Ollama inference.

**Cookie auth with Bill-App** — Bill-App issues JWT via httpOnly cookie. A shared `httpx.AsyncClient` holds the session after login. All tool calls automatically carry the cookie — no per-request token management needed.

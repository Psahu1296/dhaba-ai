# Dhaba AI

AI-powered business intelligence layer on top of a real production dhaba (Indian restaurant) POS system. Built as a portfolio project demonstrating RAG, tool calling, LangGraph agents, and streaming — all on live data.

---

## What it does

The owner can ask natural language questions about their business and get accurate, data-backed answers in real time:

- *"What item sold most today?"*
- *"Who owes us money?"*
- *"Show me revenue trend for the last 7 days"*
- *"What time did we get the most orders yesterday?"*
- *"How much chai was sold this week?"*
- *"Which day had the best revenue recently?"*

---

## Architecture

```
React Frontend (Vite + Tailwind)
        │
        │  POST /agent/chat/stream
        ▼
FastAPI Backend (port 8001)
        │
        ▼
LangGraph ReAct Agent
  ├── Tool Node → Bill-App Express API (live POS data)
  └── LLM Node → Ollama / OpenAI
        │
        ├── ChromaDB (dish menu embeddings + daily summaries)
        └── MemorySaver (conversation memory per session)
```

**Data flow:** User asks a question → LangGraph agent reasons about which tool(s) to call → calls live Bill-App API endpoints → LLM synthesizes a response → streams back token by token.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind v4 |
| Backend | FastAPI, Python 3.14 |
| Agent | LangGraph (ReAct loop), LangChain |
| LLM | Ollama (local) / OpenAI-compatible |
| Vector DB | ChromaDB (persistent) |
| Embeddings | nomic-embed-text via Ollama |
| Tracing | LangSmith |
| POS System | Bill-App (Electron + Express + MongoDB) |

---

## Features

### Two chat modes
- **Stream mode** — fast, stateless, streams tokens live
- **Agent mode** — LangGraph multi-step reasoning, conversation memory, tool calling

### 13 tools wired to live POS API

| Tool | Data |
|---|---|
| `get_dashboard_kpis` | Today's revenue, order count, % change |
| `get_revenue` | Earnings for day / week / month / year |
| `get_earnings_history` | Multi-period time series for trend analysis |
| `get_todays_top_items` | Items sold most on any given date |
| `get_peak_hours_today` | Busiest order hours on any given date |
| `get_top_dishes` | All-time bestsellers |
| `get_orders` | Order list with date and status filters |
| `get_expenses` | Expense records with date range filter |
| `get_customer_balance` | Outstanding balance for a customer |
| `get_all_customer_ledgers` | All customer dues and credit records |
| `get_consumables_summary` | Tea / gutka / cigarette usage breakdown |
| `search_dishes` | Semantic search over full menu (RAG) |
| `search_daily_history` | Semantic search over historical daily summaries (RAG) |

### RAG pipeline
- 48 dishes embedded with nomic-embed-text into ChromaDB
- Daily summary documents (revenue, top items, peak hours) auto-embedded every night at 00:30 IST via APScheduler
- Enables historical pattern queries without making multiple API calls

### Streaming agent
- LangGraph agent streams final answer token by token after tools resolve
- Loading indicator during tool execution phase
- Session memory maintained per `session_id` (MemorySaver)

---

## Project structure

```
dhaba-ai/
├── main.py              # FastAPI app, routes, CORS, auth middleware, scheduler
├── graph.py             # LangGraph ReAct agent (StateGraph + ToolNode + MemorySaver)
├── agent.py             # Legacy streaming agent (used by /chat/stream)
├── llm.py               # LLM client setup
├── config.py            # Env var loading
├── requirements.txt
├── tools/
│   ├── bill_app.py      # All Bill-App API calls (httpx client, cookie auth)
│   ├── lc_tools.py      # LangChain @tool wrappers + ALL_TOOLS list
│   ├── definitions.py   # OpenAI-format tool schemas (legacy agent)
│   ├── embedder.py      # One-time dish menu embedder
│   ├── daily_embedder.py# Daily summary embedder + ChromaDB search
│   └── retriever.py     # Dish semantic search
├── evals/
│   ├── questions.json   # 20 Q&A test pairs
│   ├── run.py           # Eval runner
│   └── score.py         # LLM judge (1–5 scoring)
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── hooks/useChat.ts
    │   ├── components/
    │   │   ├── MessageBubble.tsx
    │   │   └── InputBar.tsx
    │   └── types.ts
    └── package.json
```

---

## Running locally

### Prerequisites
- [Ollama](https://ollama.ai) running with `qwen3.5:4b` and `nomic-embed-text` pulled
- Bill-App backend running on port 5005
- Python 3.11+, Node 18+

### Backend

```bash
cd dhaba-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# copy and fill in env vars
cp .env.example .env

# seed dish embeddings (one time)
python3 -m tools.embedder

# run server
uvicorn main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

### Environment variables

```env
BILL_APP_URL=http://localhost:5005
BILL_APP_EMAIL=your_email
BILL_APP_PASSWORD=your_password
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3.5:4b
API_KEY=your_secret_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=dhaba-ai
```

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Health check |
| POST | `/chat` | Full JSON response (legacy agent) |
| POST | `/chat/stream` | Token stream (legacy agent) |
| POST | `/agent/chat` | LangGraph agent, full JSON |
| POST | `/agent/chat/stream` | LangGraph agent, token stream |
| GET | `/dishes/top` | Top dishes passthrough |
| GET | `/kpis` | KPIs passthrough |
| POST | `/admin/embed-day` | Manually trigger daily summary embedding |

All `/chat` and `/agent` routes require `X-API-Key` header.

---

## Evals

```bash
python3 -m evals.run      # run 20 test questions
python3 -m evals.score    # LLM judge scoring (1–5)
```

Result: **4.1 / 5.0** on 20 business questions against live data.

---

## Key design decisions

**Why LangGraph over a simple loop?** StateGraph gives explicit control over the agent's reasoning loop, makes tool execution observable in LangSmith, and supports conversation memory via checkpointing.

**Why RAG + tools?** Tools for real-time queries (today's orders, live revenue). RAG for semantic search over static data (menu) and historical summaries (trend queries that span many days).

**Why aggregate in Python, not the LLM?** `get_todays_top_items` and `get_peak_hours_today` parse and aggregate raw order JSON in Python before returning to the LLM. LLMs reliably hallucinate when asked to count/group from raw nested JSON.

**Why cookie-based auth with Bill-App?** Bill-App uses JWT via httpOnly cookie. A shared `httpx.AsyncClient` holds the session cookie after login — all tool calls automatically send it without per-request token management.

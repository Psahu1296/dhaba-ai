# Dhaba AI — Architecture & Complete Flow

> How every user message travels through the system and becomes an AI response.
> Current as of May 2026. v2 Pipeline Architecture. Model: GPT-4.1-nano (Railway) / qwen3.5:4b (local).

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  FRONTEND (Netlify)                                              │
│  React + Vite + TypeScript                                       │
│  useAuth → useChat → MessageBubble                               │
└─────────────────────┬────────────────────────────────────────────┘
                      │  HTTPS  (Bearer JWT or X-API-Key)
┌─────────────────────▼────────────────────────────────────────────┐
│  BACKEND (Railway)                                               │
│  FastAPI + v2 Pipeline                                           │
│  main.py → pipeline/ → tools/bill_app.py                        │
│                                                                  │
│  pipeline/                                                       │
│    intent.py     ← Stage 1: classify intent                      │
│    planner.py    ← Stage 2: deterministic tool plan              │
│    executor.py   ← Stage 3: run tools directly                   │
│    verifier.py   ← Stage 4: validate results                     │
│    synthesizer.py← Stage 5: LLM formats response                 │
└──────┬──────────────────────────────────────┬────────────────────┘
       │                                      │
       │  httpx (cookie auth)                 │  asyncpg
       ▼                                      ▼
┌─────────────┐                     ┌──────────────────┐
│  Bill-App   │                     │  PostgreSQL       │
│  Express    │                     │  (Railway)        │
│  Port 5005  │                     │                  │
│  SQLite DB  │                     │  checkpoints     │
│  Real POS   │                     │  chat_logs       │
│  data       │                     │  daily_reports   │
└─────────────┘                     │  feedback        │
                                    └──────────────────┘
```

---

## Complete Flow: User Message → AI Response

### Step 1 — User types in the browser

```
InputBar (React)
  └─ user hits Enter / Send button
       └─ handleSend() → onSend(text)
            └─ sendMessage(text)  [useChat.ts]
```

Before sending, `sendMessage` checks **implicit negative** — if the user typed "wrong", "galat", "check again", it auto-flags the last assistant message with a `-1` feedback signal and fires `POST /feedback` silently.

---

### Step 2 — Auth headers attached

```typescript
// useChat.ts — getAuthHeaders()
localStorage.getItem('dhaba_auth')    // { token, role, name }
→ { Authorization: "Bearer <jwt>" }

// Falls back to VITE_API_KEY if no JWT:
→ { "X-API-Key": "..." }
```

---

### Step 3 — HTTP request to backend

```
POST https://dhaba-ai-production.up.railway.app/agent/chat/stream
Content-Type: application/json
Authorization: Bearer eyJ...

{
  "message": "Give me today's business report",
  "session_id": "uuid-stored-in-localstorage"
}
```

The response is a **chunked stream** — tokens arrive as they're generated.

---

### Step 4 — FastAPI auth check

```python
# main.py — get_current_user dependency
async def get_current_user(credentials):
    if credentials:
        # JWT path — Login-based users
        payload = jwt.decode(token, JWT_SECRET)
        return {"email": payload["sub"], "role": payload["role"]}
    else:
        # API key path — direct API access
        if key == API_KEY:
            return {"email": "api", "role": "admin"}
        raise HTTPException(401)
```

**Role determines what data the AI can access:**
- `admin` → full access (revenue, expenses, customer balances, reports)
- `staff` → orders, dishes, menu, peak hours only

---

### Step 5 — v2 Pipeline invoked

```python
# main.py → /agent/chat/stream route
async def agent_stream(body, user=Depends(get_current_user)):
    async for token in run_pipeline_stream(body.message, body.session_id, user["role"]):
        yield token
```

`run_pipeline_stream` runs Stages 1–4 deterministically, then streams Stage 5.

---

### Step 6 — Stage 1: Intent Classifier

```python
# pipeline/intent.py
_llm = ChatOpenAI(...).with_structured_output(_Schema, method="json_mode")

result = await _llm.ainvoke([
    SystemMessage(content=_PROMPT),
    HumanMessage(content="Give me today's business report"),
])
# → IntentResult { intent: "daily_report", date_hint: "today", confidence: 1.0 }
```

A small LLM call that maps the query to a typed intent. Returns structured output — not a free-form string.

**14 intents:** `daily_report`, `past_report`, `revenue`, `expenses`, `top_dishes`, `todays_items`, `peak_hours`, `customer_dues`, `customer_balance`, `orders`, `menu`, `consumables`, `historical_trend`, `general`

---

### Step 7 — Stage 2: Workflow Planner (zero LLM)

```python
# pipeline/planner.py — pure Python, deterministic
if intent == "daily_report":
    steps = [
        { "tool_name": "get_dashboard_kpis",  "args": {} },
        { "tool_name": "get_todays_top_items", "args": {"date": "2026-05-23"} },
        { "tool_name": "get_peak_hours_today", "args": {"date": "2026-05-23"} },
        { "tool_name": "get_expenses",         "args": {"from_date": "2026-05-23", "to_date": "2026-05-23"} },
    ]
```

Python dict maps intent → tool list. Dates are resolved in Python (not by the LLM). No LLM call. Same input always produces same output.

---

### Step 8 — Stage 3: Tool Executor

```python
# pipeline/executor.py
_REGISTRY = {
    "get_dashboard_kpis": lambda a: get_dashboard_kpis(),
    "get_expenses":        lambda a: get_expenses(a.get("from_date"), a.get("to_date")),
    ...
}

for step in plan["steps"]:
    raw = _REGISTRY[step["tool_name"]](step["args"])
    results[step["tool_name"]] = await raw if inspect.isawaitable(raw) else raw
```

Tools are called directly against `tools/bill_app.py` — **no LLM involvement, no LangChain ToolNode**. Results are raw Python dicts, not TOON-encoded strings.

**Bill-App session management:**
```python
# tools/bill_app.py — _request()
async def _request(method, url, **kwargs):
    response = await _client.request(method, url, **kwargs)
    if response.status_code == 401:
        await login()  # re-authenticate silently, retry once
        response = await _client.request(method, url, **kwargs)
    return response
```

---

### Step 9 — Stage 4: Verification Layer

```python
# pipeline/verifier.py
_REQUIRED = {
    "daily_report": {"get_dashboard_kpis"},
    "expenses":     {"get_expenses"},
    ...
}

# If a required tool errored → passed=False → synthesizer returns safe error
failed_required = _REQUIRED[intent] & set(errors.keys())
if failed_required:
    passed = False
```

Rule-based checks: did required tools succeed? Are all tools down (Bill-App unreachable)? Returns `{ data, issues, passed }`.

Empty results (`expenses=[]`, `orders=[]`) are **not** treated as errors — these are valid business states.

---

### Step 10 — Stage 5: Response Synthesizer (streams)

```python
# pipeline/synthesizer.py — uses Ollama native API directly
async def synthesize_stream(messages):
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", _OLLAMA_URL,
            json={"model": LLM_MODEL, "messages": messages, "think": False, "stream": True}
        ) as r:
            async for line in r.aiter_lines():
                token = json.loads(line).get("message", {}).get("content", "")
                if token:
                    yield token
```

The LLM receives **clean verified JSON** (not TOON-compressed text). Its only job is formatting — no tool access, no orchestration decisions.

`think: False` disables qwen3's chain-of-thought locally. On Railway the model is GPT-4.1-nano which has no thinking mode.

---

### Step 11 — Tokens stream back to frontend

```python
# main.py
return StreamingResponse(
    run_pipeline_stream(message, session_id, role),
    media_type="text/plain"
)
```

Stages 1–4 complete before the first token arrives. Once synthesis starts, tokens stream directly from Ollama/OpenAI to the client.

---

### Step 12 — Frontend receives and renders tokens

```typescript
// useChat.ts — sendAgent()
const reader = res.body!.getReader()
const decoder = new TextDecoder()

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  const token = decoder.decode(value)
  setMessages(prev => prev.map(m =>
    m.id === assistantId
      ? { ...m, content: m.content + token, lastTokenAt: Date.now() }
      : m
  ))
}
```

**"Fetching data..." chip** — Stages 1–4 are deterministic but take 1–3s (tool API calls). If `lastTokenAt` hasn't updated for 600ms while `isStreaming` is true, `MessageBubble` shows an amber "Fetching data…" chip.

---

### Step 13 — Message rendered

```
MessageBubble (React):
  - Markdown parsed: **bold**, tables, bullet lists, headers, code blocks
  - After streaming ends:
    → FeedbackBar appears (thumbs up / thumbs down)
    → Thumbs down → correction textarea → POST /feedback
```

---

### Step 14 — Feedback logged (if given)

```
POST /feedback
{
  session_id: "uuid",
  query: "Give me today's business report",
  response: "Strong day — ₹2,100...",
  rating: 1,           // 1 = helpful, -1 = wrong
  source: "explicit",  // or "implicit" (auto-detected from next message)
  correction: null
}
→ Stored in Postgres feedback table
```

---

## Why v2 Pipeline vs ReAct Agent

| Concern | Old ReAct Agent (`graph.py`) | v2 Pipeline (`pipeline/`) |
|---------|------------------------------|---------------------------|
| Tool routing | LLM decides dynamically | Python dict (deterministic) |
| Execution | LLM calls tools in a loop | Executor runs plan directly |
| Context truncation | `messages[-8:]` — breaks multi-step reasoning | Stateless per invocation |
| Failures | Silent wrong answers | Verifier blocks bad responses |
| Debugging | Trace LLM chain-of-thought | Inspect state at each stage |
| Hallucination risk | High (LLM orchestrates everything) | Low (LLM only formats verified data) |

The old `graph.py` ReAct agent is still in the codebase but no longer handles `/agent/chat` routes.

---

## Auth Flow (Login → Token → Request)

```
1. User opens app
   └─ useAuth: reads localStorage("dhaba_auth")
        └─ if null → show <LoginPage>

2. User enters Bill-App credentials (same as POS login)
   └─ POST /login { email, password }
        └─ FastAPI → POST bill-app/api/user/login
             └─ Bill-App verifies → returns user data
                  └─ FastAPI issues dhaba-ai JWT:
                       { sub: email, role: "admin"|"staff", exp: 24h }
                  └─ Stored in localStorage("dhaba_auth")

3. Every subsequent request:
   └─ Authorization: Bearer <jwt>
        └─ get_current_user extracts role
             └─ Role passed into pipeline as state["role"]
                  └─ OWNER_SCOPE or STAFF_SCOPE added to synthesizer prompt
```

---

## Session & Memory Flow

```
Session ID:
  - Generated once: crypto.randomUUID()
  - Stored: localStorage("dhaba_session_id")
  - Sent: every /agent/chat/stream request as session_id
  - Used as: LangGraph thread_id → Postgres checkpoint key (prefixed "pipeline-")

What's saved per session in Postgres:
  - Pipeline state snapshots (intent, plan, results, response)
  - Full conversation thread state via LangGraph checkpointer

Effect:
  - Refresh page → session_id still in localStorage → state retrievable
  - "Clear Chat" → new UUID → new thread → fresh start
```

---

## The 14 Available Tools

| Tool | Triggers | Bill-App endpoint |
|------|----------|------------------|
| `resolve_date` | "kal", "yesterday", "last week" | (pure Python, no API) |
| `get_dashboard_kpis` | "today's revenue", "KPIs", "aaj kitna hua" | `GET /api/earnings/dashboard` |
| `get_todays_top_items` | "top items", "best seller today", "kal ke top items" | `GET /api/order` → Python aggregation |
| `get_peak_hours_today` | "peak hours", "busiest time", "busy kab tha" | `GET /api/order` → Python aggregation |
| `get_earnings_history` | "last 7 days", "pichle hafte ka data" | `GET /api/earnings/day` |
| `get_expenses` | "expenses", "kharcha", "cost today" | `GET /api/expenses` → Python date filter |
| `get_orders` | "active orders", "pending orders", "show orders" | `GET /api/order` |
| `get_top_dishes` | "best dish overall", "most popular" | `GET /api/dishes/frequent` |
| `get_all_dishes` | "full menu", "veg dishes", "non-veg list" | `GET /api/dishes` |
| `search_dishes` | "any biryani?", "egg items", "find [dish]" | ChromaDB semantic search |
| `get_customer_balance` | user gives a phone number | `GET /api/ledger/:phone` |
| `get_all_customer_ledgers` | "who owes us?", "customers with dues" | `GET /api/ledger/all` → Python filter |
| `get_consumables_summary` | "chai kitni biki", "gutka usage" | `GET /api/consumables/summary/day` |
| `search_daily_history` | "best day last month", "historical trends" | ChromaDB daily summaries |

In v2, tools are called via `pipeline/executor.py` directly — not through LangChain `@tool` wrappers.

---

## Data Fixes in Python (Bill-App API Quirks)

| Issue | Fix |
|-------|-----|
| `/api/expenses` ignores `from`/`to` params — returns all-time data | Fetch all, filter by `expenseDate` in Python |
| `/api/earnings/dashboard` field `total` is ambiguous | Renamed to `today_revenue_rupees`, `week_revenue_rupees` etc. |
| `/api/ledger/all` returns full transaction history — huge payload | Strip `transactions[]`, keep only `name`, `phone`, `balance_due_rupees` |
| `get_todays_top_items` / `get_peak_hours_today` — no endpoint exists | Built in Python: fetch orders by date, aggregate items and timestamps |

---

## Deployment

| Component | Host | URL |
|-----------|------|-----|
| Frontend | Netlify | `dhaba-ai.netlify.app` |
| Backend + Pipeline | Railway | `dhaba-ai-production.up.railway.app` |
| PostgreSQL | Railway | Internal Railway DB |
| Bill-App | Railway / Tunnel | Configured via `BILL_APP_URL` env var |

**Environment variables on Railway:**
```
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-nano
BILL_APP_URL=http://...
BILL_APP_EMAIL=admin@gmail.com
BILL_APP_PASSWORD=...
DATABASE_URL=postgresql://...
API_KEY=...
JWT_SECRET=...
ALLOWED_ORIGINS=https://dhaba-ai.netlify.app
```

---

## Run Locally

```bash
cd /Volumes/DevSSD/projects/ai-projects/dhaba-ai
source .venv/bin/activate

# Prerequisites: Bill-App on port 5005, Ollama running (ollama serve)
uvicorn main:app --reload --port 8001

# Run flow tests against Railway
python3 evals/test_flows.py

# Run full eval suite
python3 evals/run_remote.py && python3 evals/score.py
```

---

## Eval Results (as of May 2026)

```
Flow tests (12 queries, specific tool routing checks):
  12/12 ✅ — all passing

Keyword eval (40 questions):
  Score: 5.0/5.0 ✅

Architecture improvements in v2:
  1. Deterministic tool routing (planner.py) → no mis-routing
  2. Verification layer → no hallucinated numbers when Bill-App is down
  3. Removed messages[-8:] truncation → no broken multi-step reasoning
  4. LLM only at intent classification + response synthesis → fewer failure points
  5. Synthesizer gets clean JSON (not TOON) → better formatting quality
```

# Dhaba AI — Sharpening Plan (v3)

> Goal: maximum answer accuracy and production robustness on the **deterministic pipeline**,
> tuned for **gpt-4.1-nano** as the production model.
>
> This is NOT a rewrite. The v2 pipeline (intent → planner → executor → verifier → synthesizer)
> in `pipeline/` is the right architecture. v3 sharpens it: fixes silent correctness bugs,
> makes all math deterministic, hardens the intent layer (the accuracy bottleneck), and builds
> an eval + feedback loop that can actually *measure* correctness.
>
> Previous roadmap: `improvement.md` (v2 — shipped). This file supersedes it for new work.

---

## 0. Production reality (read this first)

What is actually running in prod today:

| Endpoint | Handler | Path | Status |
|---|---|---|---|
| `POST /agent/chat` | `run_pipeline` | `pipeline/graph.py` | **PROD — the real path** |
| `POST /agent/chat/stream` | `run_pipeline_stream` | `pipeline/graph.py` | **PROD** |
| `POST /chat` | `run_agent` | `agent.py` | legacy, dead-ish |
| `POST /chat/stream` | `run_agent_stream` | `agent.py` | legacy, dead-ish |
| (none) | `run_graph` | `graph.py` | **DEAD — imported, never routed** |

Consequences that matter for this plan:
- The LangGraph ReAct agent in `graph.py` is no longer used. Its IST date handling, TOON
  encoding, and few-shot prompt are all bypassed in prod.
- `evals/ground_truth.py` imports `run_graph` — **it tests the dead path.** Our numeric eval is
  currently validating code that serves zero traffic. (Fix in Phase 3.)
- `CLAUDE.md` still describes `/agent/chat` as the LangGraph ReAct agent. Stale. Update it.

**Model:** prod uses `gpt-4.1-nano` (OpenAI), so `_is_ollama` is `False`. This unlocks:
- Native **structured outputs** (`json_schema`, strict) — far more reliable than `json_mode`.
- Cheap enough ($0.10/1M in, $0.40/1M out) to afford an **LLM-judge eval** and an
  **escalation tier** to a stronger model for hard queries, all inside the <$20/mo budget.

---

## 1. Guiding principles

1. **The LLM never does arithmetic or date math.** Every number in an answer is computed in
   Python and handed to the model as a labelled fact. The model only writes prose. This is
   already 80% true — v3 closes the remaining gaps (trends, money rounding, "today").
2. **Measure before tuning.** No prompt change ships without an eval number moving. Today's
   "5.0/5.0" is keyword-coverage, not correctness — fix the ruler first (Phase 3).
3. **Fail loud, not wrong.** A blocked "data unavailable" is acceptable. A confident wrong
   number is not. Verifier gets teeth (Phase 5).
4. **Determinism over autonomy.** Keep tool selection in the planner, not the model. Where the
   model still gets latitude (intent, synthesis), constrain it with schemas and few-shots.

---

## 2. New dependencies

Add to `requirements.txt`. Each earns its place:

| Library | Pin | Why |
|---|---|---|
| `tenacity` | `>=8.2` | Declarative retry/backoff for Bill-App tool calls and LLM calls. Replaces the hand-rolled retry loop in `login()`. Robustness. |
| `rapidfuzz` | `>=3.6` | Fast fuzzy string matching. Deterministic intent pre-filter (phone/menu/keyword routing before spending an LLM call) and fuzzy customer/dish name matching. |
| `pydantic` | already in | Lean on it harder — validate the *synthesized* answer's numbers against the data block, and define strict intent schema. |

Deliberately **not** adding:
- `pendulum` / `arrow` — stdlib `zoneinfo` already does what we need; the bug is that we don't
  *use* it, not that it's missing.
- `numpy` — `statistics` (stdlib) covers mean/stdev/trend. No array math heavy enough to justify numpy.
- `ragas` — defer. Useful later for evaluating the daily-history semantic search, but heavyweight
  and not on the critical path. Revisit in a dedicated RAG-eval pass.

Money will use stdlib `decimal.Decimal` — no dependency.

---

## 3. Phase 0 — Correctness bugs (ship first, they produce silently wrong answers)

### 0.1 — IST date resolution in the pipeline
**Files:** `pipeline/planner.py`, `tools/processors.py`
**Problem:** Both re-implement date logic with bare `date.today()`. On Railway (UTC), during
IST 00:00–05:30 "today" resolves to yesterday. You already solved this in `tools/dates.py`
(`today_ist()`), but the pipeline doesn't import it.
**Fix:**
- In `planner.py`, delete the local `_resolve_date` and import `resolve_day` / `resolve_range`
  from `tools.dates`. Replace `date.today()` with `today_ist()`.
- In `processors.py`, replace every `_date.today()` with `today_ist()` (import from `tools.dates`).
**Test:** set `TZ=UTC`, freeze clock to 02:00 IST equivalent, assert `daily_report` queries today's IST date.

### 0.2 — Single source of "today" inside one report
**File:** `pipeline/planner.py` (`daily_report` branch)
**Problem:** top-items/peak/expenses get planner's `today` (UTC) while revenue comes from
Bill-App's dashboard (its own clock). Across midnight they describe different days.
**Fix:** resolve `today = today_ist()` once at the top of `plan_workflow` and pass that one value
to every step. After 0.1 this falls out naturally — just verify the `daily_report` branch uses the
shared variable.

### 0.3 — Verifier `_REQUIRED` is out of sync with the planner
**File:** `pipeline/verifier.py`
**Problem:** `_REQUIRED["past_report"] = {"get_earnings_history"}` but the planner runs
`get_daily_summary` for that intent. `revenue` requires both KPIs *and* history but the planner
runs only one. The guard only blocks on a required tool *erroring*, so for these intents it's a
silent no-op — it verifies nothing.
**Fix:** rewrite `_REQUIRED` to match what `plan_workflow` actually emits per intent:
```python
_REQUIRED = {
    "daily_report":     {"get_dashboard_kpis"},
    "past_report":      {"get_daily_summary"},
    "revenue":          {"get_dashboard_kpis"},   # or get_earnings_history — match the branch taken
    "expenses":         {"get_expenses"},
    "top_dishes":       {"get_top_dishes"},
    "todays_items":     {"get_todays_top_items"},
    "peak_hours":       {"get_peak_hours_today"},
    "customer_dues":    {"get_all_customer_ledgers"},
    "customer_balance": {"get_customer_balance"},
    "orders":           {"get_orders"},
    "menu":             {"get_all_dishes"},
    "consumables":      {"get_consumables_summary"},
    "historical_trend": {"get_earnings_range"},
    "general":          set(),
}
```
Note `revenue` runs *either* KPIs *or* history depending on period — make the required set the
union-aware check (block only if the tool the planner actually chose is missing). Simplest: have
the planner stamp `state["primary_tool"]` and verify that one succeeded.

### 0.4 — TOON is dead on the prod endpoint (decide: wire or remove)
**Files:** `pipeline/graph.py` (`_build_messages`), `main.py` (`/agent/chat` response)
**Problem:** the pipeline sends `json.dumps(verified["data"])` to the synthesizer — `codec` is
never called, never reset. The `toon_chars_saved` field returned by `/agent/chat` is meaningless.
**Decision:** with gpt-4.1-nano, raw JSON for these small payloads is fine and arguably reasons
better (see `improvement.md` §12, which already concluded "v2 uses clean JSON"). So:
- **Remove** `toon_chars_saved` from the `/agent/chat` and `/agent/chat/stream` responses, and
  drop the savings badge from the frontend for these endpoints — it's reporting a number that
  isn't real.
- Keep TOON only where it's genuinely used, or retire it entirely. Don't ship a metric the
  prod path doesn't produce.

---

## 4. Phase 1 — Calculation hardening (every number is Python-computed)

### 1.1 — Currency as `Decimal`, not `float`
**Files:** `tools/processors.py`, `tools/bill_app.py` aggregation helpers
**Problem:** revenue/expense sums use float (`sum(o.get("bills",{}).get("total",0) ...)`).
Float drift produces ₹2,399.9999 → displayed wrong, and `==` comparisons in evals get flaky.
**Fix:** parse money into `Decimal` at the boundary, sum in `Decimal`, round with
`quantize(Decimal("1"))` to whole rupees before handing to the LLM. One helper:
```python
from decimal import Decimal, ROUND_HALF_UP
def rupees(x) -> int:
    return int(Decimal(str(x or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
```
Apply in `get_daily_summary` fallback revenue, `get_expenses` totals, `flag_expenses`,
`extract_period_revenue`, `slim_*` sums.

### 1.2 — Pre-compute trend answers (don't hand arrays to the model)
**Files:** `pipeline/executor.py` (`_post_process`), `tools/processors.py`
**Problem:** `historical_trend` only pre-computes when the query hits the `find_peak_day`
keyword list. Other trend queries ("how's this month trending", "average daily revenue",
"which week was best") pass a raw multi-day array to nano, which will fumble the arithmetic.
**Fix:** add deterministic trend stats in `processors.py` using stdlib `statistics`:
```python
import statistics
def summarize_trend(entries):  # entries: [{date, revenue_rupees}]
    revs = [e["revenue_rupees"] for e in entries if e.get("revenue_rupees") is not None]
    if not revs: return {"note": "no data"}
    return {
        "days": len(revs),
        "total_rupees": sum(revs),
        "avg_daily_rupees": round(statistics.mean(revs)),
        "best_day": max(entries, key=lambda e: e["revenue_rupees"]),
        "worst_day": min(entries, key=lambda e: e["revenue_rupees"]),
        "trend": "up" if revs[-1] > revs[0] else "down" if revs[-1] < revs[0] else "flat",
        "stdev_rupees": round(statistics.pstdev(revs)) if len(revs) > 1 else 0,
    }
```
Always run this for `historical_trend`, regardless of keywords. The model then narrates a
verdict instead of computing one.

### 1.3 — Validate synthesized numbers against the data block (anti-hallucination tripwire)
**File:** new `pipeline/guard.py`, called from `pipeline/graph.py` after synthesis (non-stream),
and as a post-check on the buffered stream.
**Idea:** extract every ₹-number the model wrote, and confirm each appears in (or is derivable
from) `verified["data"]`. If the model emitted a rupee figure that isn't grounded, log it and —
for the non-stream path — regenerate once with a stricter instruction. This is cheap with nano
and directly attacks the "confident wrong number" failure mode.
```python
import re
def ungrounded_numbers(answer: str, data: dict) -> list[str]:
    nums_in_data = set(re.findall(r"\d[\d,]*", json.dumps(data)))
    nums_in_data = {n.replace(",", "") for n in nums_in_data}
    out = []
    for m in re.findall(r"₹\s*([\d,]+)", answer):
        if m.replace(",", "") not in nums_in_data:
            out.append(m)
    return out
```
Start in **log-only** mode (measure how often it fires) before enabling regeneration.

---

## 5. Phase 2 — Intent layer (the single biggest accuracy lever)

If intent is wrong, the planner runs the wrong tools and everything downstream is wrong. This is
nano's main failure mode and it's currently one unguarded call.

### 2.1 — Switch to native structured outputs (`json_schema`, strict)
**File:** `pipeline/intent.py`
**Problem:** uses `with_structured_output(_Schema, method="json_mode")` — json_mode is the weak
mode. nano supports strict `json_schema`.
**Fix:**
```python
_llm = _base.with_structured_output(_Schema, method="json_schema", strict=True)
```
Removes the Ollama `think:false` branch on the prod path. More reliable parsing, fewer retries.

### 2.2 — Few-shot the intent prompt
**File:** `pipeline/intent.py`
**Problem:** the intent prompt has zero worked examples. The rich few-shots live in the **dead**
`graph.py` system prompt.
**Fix:** add 12–15 labelled examples to `_PROMPT`, one per intent plus the tricky boundaries
(date present → `todays_items` not `top_dishes`; "kaisa raha aaj" → `daily_report` not `general`;
follow-ups → `general`; "drinks/chai" → `consumables`). Mine these from real misclassifications
once tracing is on (Phase 5) and from feedback corrections (Phase 4).

### 2.3 — Deterministic pre-filter before the LLM call
**File:** new `pipeline/intent_rules.py`, called at the top of `classify_intent`
**Idea:** unambiguous queries shouldn't cost an LLM call or risk misclassification:
- contains a 10-digit phone number → `customer_balance` (extract phone), confidence 1.0
- matches `rapidfuzz` against a small phrase set ("menu", "price list", "rate kya hai") → `menu`
- single greeting token ("hi", "namaste", "thanks") → `general`
Only fall through to the LLM when no rule fires. Faster, cheaper, deterministic on the easy cases.

### 2.4 — Confidence routing
**Files:** `pipeline/intent.py` (already returns `confidence`), `pipeline/graph.py`
**Problem:** `confidence` is captured and never used.
**Fix:** in `_run_stages`, if `confidence < 0.5` and intent isn't `general`, either:
- ask one clarifying question (return a fixed prompt, don't fabricate data), or
- escalate the classification to the stronger model (2.5).
Pick clarify for ambiguous, escalate for complex. Log every low-confidence event.

### 2.5 — Escalation tier for hard intents
**Files:** `config.py` (`ESCALATION_MODEL=gpt-4.1-mini`), `pipeline/intent.py`, `pipeline/synthesizer.py`
**Idea:** keep nano as default; route only `historical_trend`, low-confidence classifications, and
multi-tool reports to `gpt-4.1-mini` for the synthesis step. These are a small fraction of traffic,
so cost stays trivial, but quality on the hardest answers jumps. Gate behind an env flag so it's
easy to A/B.

---

## 6. Phase 3 — Evals that measure correctness (fix the ruler)

### 3.1 — Point every eval at the prod pipeline
**Files:** `evals/ground_truth.py`, `evals/run.py`, `evals/run_remote.py`
**Problem:** `ground_truth.py` imports `run_graph` (dead path). `run_remote.py` hits Railway
`/agent/chat` (correct). They're testing different code.
**Fix:** `ground_truth.py` should call `run_pipeline` (local) or hit `/agent/chat` (remote), same
as the live path. Delete `run_graph` usage everywhere in evals.

### 3.2 — Wire numeric ground-truth into the scorer
**Files:** `evals/score.py`, `evals/ground_truth.py`, `evals/questions.json`
**Problem:** `score.py` is keyword-coverage only. `ground_truth.py` has real numeric checks
(`_num_in`) but runs as a separate script and isn't part of the headline score.
**Fix:** merge. For questions that have a known numeric answer (revenue, expense total, order
count), score = "does the answer contain the live value from the API?" Keep keyword coverage only
for qualitative answers (menu lists, tone). Report two numbers: **numeric accuracy** and
**coverage**. Numeric accuracy is the one that matters.

### 3.3 — Dedicated intent-classification eval
**File:** new `evals/intent_eval.py`
**Why:** intent is the top of the funnel and has no metric today. Build a labelled set
(query → expected intent), run `classify_intent` over it, report a confusion matrix. This is the
fastest feedback loop for Phase 2 work — you can iterate the prompt in seconds without running
the whole pipeline.

### 3.4 — Turn on the LLM judge (cheap model)
**File:** `evals/score.py` (the `--llm-judge` path already exists)
**Fix:** it was disabled because the local thinking model was too slow. On prod you're on OpenAI
already — run the judge with `gpt-4o-mini` or `gpt-4.1-mini`. ~$0.001/question × 45 = negligible.
Use it for the qualitative half (tone, insight, did-it-actually-answer) where keywords are blind.

### 3.5 — Make it CI-friendly
**File:** `evals/ground_truth.py` already exits 0/1. Add a `make eval` or a GitHub Action that
runs numeric + intent evals on push. A regression in accuracy should fail the build.

---

## 7. Phase 4 — Feedback flywheel (you already built half of it)

`get_feedback_stats` already surfaces `pending_eval_candidates` from thumbs-down + corrections.
Nothing consumes them. Close the loop:

### 4.1 — Corrections → eval cases
**File:** new `evals/from_feedback.py`
Pull corrected Q&A pairs, dedupe, append to `questions.json` (or a `regressions.json`). Every real
mistake the owner corrects becomes a permanent regression test.

### 4.2 — Corrections → intent few-shots
**File:** feeds Phase 2.2
When a correction reveals a misroute (wrong tool ran), add that query as a few-shot to the intent
prompt with the right label. The system gets better at exactly the mistakes it actually made.

### 4.3 — Implicit feedback signal
**File:** frontend + `/feedback`
Treat "user immediately rephrases the same question" or "user abandons" as implicit negative
(`source="implicit"`). You already have the `source` column. This widens the correction funnel
without asking the owner to rate anything.

---

## 8. Phase 5 — Robustness

### 5.1 — Retries with `tenacity`
**Files:** `tools/bill_app.py`, `pipeline/synthesizer.py`, `pipeline/intent.py`
Wrap Bill-App requests and LLM calls in `@retry(stop=stop_after_attempt(3), wait=wait_exponential())`.
Replace the hand-rolled retry loop in `login()`. Transient 429/5xx/network blips stop becoming
user-visible failures.

### 5.2 — Verifier with teeth (data sanity, not just exceptions)
**File:** `pipeline/verifier.py`
Add per-intent sanity checks beyond "did the tool throw":
- `revenue`/`daily_report`: if `order_count > 0` but `revenue == 0` → suspect, block or flag.
- `past_report`: if the `get_daily_summary` fallback returned all-zero AND orders exist → flag.
- numeric fields expected non-null are non-null.
Keep empty-as-valid for expenses/orders/ledgers (already correct).

### 5.3 — Follow-ups need data, not just prose
**Files:** `pipeline/memory.py`, `pipeline/graph.py`
**Problem:** memory stores only the assistant's prose. "Tell me more about the second customer"
→ classified `general` → no tool → model improvises from its own earlier text.
**Fix:** also persist the last turn's `verified["data"]` (compact) keyed by session. When intent is
`general` *and* the query is a follow-up reference, feed that stored data block to the synthesizer
so the answer stands on real numbers.

### 5.4 — Persistent tracing (LangSmith is already a dependency)
**Files:** `config.py`, `pipeline/graph.py`
`langsmith==0.8.5` is installed and unused. Set `LANGCHAIN_TRACING_V2=true` + project, and/or
write each run's `{intent, confidence, plan, tools, errors, verified.passed, latency, low_conf}`
to a Postgres `pipeline_traces` table. Today `_trace` only logs to stdout — you can't replay a
bad answer. This underpins Phases 2 and 4 (you mine traces for few-shots and regressions).

### 5.5 — Retire dead code
**Files:** `graph.py`, `agent.py`, `tools/definitions.py`, `/chat` routes, `llm.py`
Once evals point at the pipeline (3.1), delete or clearly quarantine the ReAct agent and simple
agent. They confuse maintenance and caused the ground-truth eval to test the wrong path. Update
`CLAUDE.md` to describe the pipeline as the prod path.

---

## 9. Implementation order (milestones)

Each milestone is independently shippable and leaves the system better.

| # | Milestone | Phases | Why this order |
|---|---|---|---|
| M1 | **Stop being silently wrong** | 0.1–0.4 | Correctness bugs first. Small diffs, high impact. |
| M2 | **Trust the ruler** | 3.1–3.2, 3.3 | Can't improve accuracy without measuring it. Point evals at prod, add numeric + intent metrics. |
| M3 | **All math in Python** | 1.1–1.3 | Decimal money, pre-computed trends, hallucination tripwire. Evals from M2 prove it. |
| M4 | **Sharpen intent** | 2.1–2.5 | The biggest lever, now measurable via M2's intent eval. |
| M5 | **Close the loop** | 4.1–4.3, 3.4 | Feedback → evals → few-shots. Compounding gains. |
| M6 | **Harden + clean** | 5.1–5.5 | Retries, verifier teeth, tracing, kill dead code. |

Do **not** skip M2. Today's 5.0/5.0 is keyword coverage — tuning prompts against it optimizes
vocabulary, not correctness.

---

## 10. Budget & risk notes

- **Cost:** nano default + occasional `gpt-4.1-mini` escalation + LLM-judge on 45 eval questions
  is well under $20/mo at this traffic. The judge runs only when you run evals, not per request.
- **Risk — over-blocking:** the hardened verifier (5.2) and number tripwire (1.3) could refuse
  valid answers. Mitigate: ship both in **log-only** mode first, read a week of traces, then enable
  enforcement once false-positive rate is known.
- **Risk — escalation cost creep:** gate the escalation tier (2.5) behind an env flag and log how
  often it fires. If >20% of traffic escalates, the intent confidence threshold is mis-tuned.
- **Teaching note:** per project rules, Python changes get walked through file-by-file (what/where/
  why → code block → you type → test command), not edited directly. This doc is the map; we
  implement one milestone at a time.

---

## 11. Open questions to resolve before M1

1. **TOON (0.4):** remove the metric from the prod endpoint, or invest in wiring TOON into the
   pipeline? Recommendation: remove — clean JSON reasons better on nano and the v2 doc already
   reached this conclusion.
2. **Escalation model (2.5):** `gpt-4.1-mini` vs `gpt-4o-mini` for the hard tier? Both in budget;
   pick one and A/B via the eval set.
3. **Clarify vs escalate (2.4):** for low-confidence intent, default to a clarifying question
   (safer, slower) or silent escalation (smoother, costs a call)? Recommendation: clarify for
   truly ambiguous, escalate for complex-but-clear.
</content>
</invoke>

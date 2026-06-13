import json
import time
import logging
from pipeline import memory
from pipeline.intent import classify_intent
from pipeline.planner import plan_workflow
from pipeline.executor import execute_tools
from pipeline.verifier import verify_results
from pipeline.synthesizer import synthesize_stream, _SYSTEM
from pipeline import guard

logger = logging.getLogger(__name__)

# Below this classifier confidence we ask the user to clarify rather than run a
# possibly-wrong tool chain. The pre-filter and clear LLM hits sit at 0.8–1.0,
# so this only catches genuinely ambiguous queries.
_CONFIDENCE_THRESHOLD = 0.45
_CLARIFY_MSG = (
    "Samajh nahi aaya thoda — aap revenue, expenses, orders, dishes, customer dues, "
    "ya report mein se kis baare mein puchh rahe hain? Thoda saaf bata dijiye."
)


def _needs_clarification(state: dict) -> bool:
    intent = state.get("intent") or {}
    return (
        intent.get("intent") not in ("general", None)
        and float(intent.get("confidence") or 0) < _CONFIDENCE_THRESHOLD
    )


# Intents complex enough to justify the stronger (escalation) model for synthesis.
_ESCALATE_INTENTS = {"historical_trend"}


def _should_escalate(state: dict) -> bool:
    return (state.get("intent") or {}).get("intent") in _ESCALATE_INTENTS


async def init_pipeline(database_url: str):
    await memory.init(database_url)


def _trace(state: dict, latency_ms: int) -> None:
    intent = state.get("intent") or {}
    plan = state.get("plan") or {}
    raw = state.get("raw_results") or {}
    verified = state.get("verified") or {}
    logger.info(
        "pipeline | intent=%-20s conf=%.2f | tools=%s | errors=%s | verified=%s | %dms",
        intent.get("intent", "?"),
        intent.get("confidence", 0),
        [s["tool_name"] for s in plan.get("steps", [])],
        list(raw.get("errors", {}).keys()),
        verified.get("passed", "?"),
        latency_ms,
    )


def _build_messages(state: dict, query: str, history: list[dict]) -> list[dict]:
    """Assemble the messages list for the synthesizer: system + history + current turn."""
    verified = state["verified"]
    intent_name = state["intent"]["intent"]
    sys_msg = {"role": "system", "content": _SYSTEM}

    if intent_name == "general":
        return [sys_msg, *history, {"role": "user", "content": query}]

    data_str = json.dumps(verified["data"], ensure_ascii=False, indent=2)
    user_msg = (
        f'User asked: "{query}"\n\n'
        f"Verified business data:\n{data_str}\n\n"
        f"Respond in dhaba assistant tone. Lead with the key verdict (one line). Then details. Then one insight."
    )
    return [sys_msg, *history, {"role": "user", "content": user_msg}]


async def _run_stages(message: str, role: str) -> dict:
    state: dict = {
        "query": message, "role": role,
        "intent": None, "plan": None,
        "raw_results": None, "verified": None, "response": None,
    }
    state.update(await classify_intent(state))
    state.update(plan_workflow(state))
    state.update(await execute_tools(state))
    state.update(verify_results(state))
    return state


async def run_pipeline(message: str, session_id: str, role: str = "admin") -> str:
    t0 = time.monotonic()
    history = await memory.load(session_id)
    state = await _run_stages(message, role)
    _trace(state, int((time.monotonic() - t0) * 1000))

    if _needs_clarification(state):
        logger.info("pipeline | low confidence, asking to clarify | query=%r", message[:80])
        await memory.save(session_id, message, _CLARIFY_MSG)
        return _CLARIFY_MSG

    verified = state["verified"]
    if not verified["passed"]:
        return f"Data unavailable — {'; '.join(verified['issues'])}"

    messages = _build_messages(state, message, history)
    tokens: list[str] = []
    async for token in synthesize_stream(messages, escalate=_should_escalate(state)):
        tokens.append(token)
    response = "".join(tokens)
    guard.check(response, verified.get("data"), query=message)
    await memory.save(session_id, message, response)
    return response


async def run_pipeline_stream(message: str, session_id: str, role: str = "admin"):
    t0 = time.monotonic()
    history = await memory.load(session_id)
    state = await _run_stages(message, role)
    _trace(state, int((time.monotonic() - t0) * 1000))

    if _needs_clarification(state):
        logger.info("pipeline | low confidence, asking to clarify | query=%r", message[:80])
        await memory.save(session_id, message, _CLARIFY_MSG)
        yield _CLARIFY_MSG
        return

    verified = state["verified"]
    if not verified["passed"]:
        yield f"Data unavailable — {'; '.join(verified['issues'])}"
        return

    messages = _build_messages(state, message, history)

    tokens: list[str] = []
    async for token in synthesize_stream(messages, escalate=_should_escalate(state)):
        tokens.append(token)
        yield token

    full = "".join(tokens)
    guard.check(full, verified.get("data"), query=message)
    await memory.save(session_id, message, full)

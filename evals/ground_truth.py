"""
Ground-truth eval — checks AI answers contain real numbers from live API data.

Catches wrong tool routing (e.g. reading daily_earnings table instead of orders).
Run: python3 -m evals.ground_truth

Exits 0 if all pass, 1 if any fail (CI-friendly).
"""
import asyncio
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date
from tools.bill_app import (
    login,
    get_dashboard_kpis as _kpis,
    get_top_dishes as _top_dishes,
    get_expenses as _expenses,
)
from graph import run_graph


# ── Helpers ────────────────────────────────────────────────────────────────

def _num_in(expected: float, answer: str) -> bool:
    """Return True if expected number (or sensibly rounded form) is in answer."""
    clean = re.sub(r'[₹,\s]', '', answer)
    n = int(expected)
    if n == 0:
        return True  # zero is trivially present
    candidates = {
        str(n),
        str(round(n / 100) * 100),
        str(round(n / 1000) * 1000),
    }
    return any(c in clean for c in candidates if c != '0')


def _str_in(expected: str, answer: str) -> bool:
    return expected.lower() in answer.lower()


REFUSAL_PHRASES = [
    "i don't have",
    "i do not have",
    "don't have access",
    "you might want to check",
    "check your records",
    "i cannot access",
    "i can't access",
    "not available",
    "you would need to",
]

def _is_refusal(answer: str) -> bool:
    lower = answer.lower()
    return any(phrase in lower for phrase in REFUSAL_PHRASES)


# ── Ground truth fetch ──────────────────────────────────────────────────────

async def fetch_ground_truth() -> dict:
    kpis_raw = await _kpis()
    data = kpis_raw.get("data", kpis_raw)

    def _period_total(key: str) -> float:
        val = data.get(key, {})
        return float(val.get("total", 0)) if isinstance(val, dict) else 0.0

    dishes_raw = await _top_dishes(limit=3)
    dishes = (
        dishes_raw if isinstance(dishes_raw, list)
        else dishes_raw.get("data", dishes_raw.get("dishes", []))
    )
    top_dish = dishes[0].get("name", "") if dishes else ""

    today = date.today().isoformat()
    exp_raw = await _expenses(from_date=today, to_date=today)
    records = exp_raw if isinstance(exp_raw, list) else exp_raw.get("data", [])
    today_expenses = sum(float(e.get("amount", 0)) for e in records)

    return {
        "today":          _period_total("daily"),
        "weekly":         _period_total("weekly"),
        "monthly":        _period_total("monthly"),
        "yearly":         _period_total("yearly"),
        "top_dish":       top_dish,
        "today_expenses": today_expenses,
    }


# ── Check definitions ───────────────────────────────────────────────────────

CHECKS = [
    {
        "id": 1,
        "question": "What is today's revenue?",
        "key": "today",
        "type": "number",
    },
    {
        "id": 2,
        "question": "How much did we earn this week?",
        "key": "weekly",
        "type": "number",
    },
    {
        "id": 3,
        "question": "What is our revenue this month?",
        "key": "monthly",
        "type": "number",
    },
    {
        "id": 4,
        "question": "How much have we earned this year?",
        "key": "yearly",
        "type": "number",
    },
    {
        "id": 5,
        "question": "What are the top 3 best selling dishes?",
        "key": "top_dish",
        "type": "text",
    },
    {
        "id": 6,
        "question": "What are today's total expenses?",
        "key": "today_expenses",
        "type": "number",
    },
    {
        "id": 7,
        "question": "Which day had the highest revenue this month?",
        "key": None,
        "type": "no_refusal",
    },
    {
        "id": 8,
        "question": "Who owes the most money to the dhaba?",
        "key": None,
        "type": "no_refusal",
    },
]


# ── Runner ──────────────────────────────────────────────────────────────────

async def run():
    print("Fetching ground truth from live API...")
    await login()
    gt = await fetch_ground_truth()

    print("\nGround truth values:")
    print(f"  Today:          ₹{gt['today']:,.0f}")
    print(f"  Weekly:         ₹{gt['weekly']:,.0f}")
    print(f"  Monthly:        ₹{gt['monthly']:,.0f}")
    print(f"  Yearly:         ₹{gt['yearly']:,.0f}")
    print(f"  Top dish:       {gt['top_dish']}")
    print(f"  Today expenses: ₹{gt['today_expenses']:,.0f}")

    print(f"\nRunning {len(CHECKS)} checks...\n")
    print(f"{'ID':<4} {'Result':<8} {'Expected':<22} Question")
    print("─" * 85)

    passed = 0
    failures = []

    for check in CHECKS:
        answer = await run_graph(check["question"], str(uuid.uuid4()))
        expected = gt[check["key"]] if check["key"] else None

        if check["type"] == "no_refusal":
            ok = not _is_refusal(answer)
            exp_str = "answered (not refused)"
        elif check["type"] == "number":
            ok = _num_in(float(expected), answer)
            exp_str = f"₹{int(expected):,}"
        else:
            ok = _str_in(str(expected), answer)
            exp_str = str(expected)

        if ok:
            passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            failures.append({**check, "expected": exp_str, "got": answer})

        print(f"{check['id']:<4} {status:<8} {exp_str:<22} {check['question']}")

    print(f"\n{'─' * 85}")
    print(f"Result: {passed}/{len(CHECKS)} passed\n")

    if failures:
        print("Failed checks:")
        for f in failures:
            snippet = f["got"].replace("\n", " ")[:120]
            print(f"\n  [{f['id']}] {f['question']}")
            print(f"       Expected: {f['expected']}")
            print(f"       Got:      {snippet}...")

    sys.exit(0 if passed == len(CHECKS) else 1)


if __name__ == "__main__":
    asyncio.run(run())

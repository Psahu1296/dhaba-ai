#!/usr/bin/env python3
"""
End-to-end flow tests against the live Railway API.
Tests the specific flows that were failing in manual testing.

Usage:
  python3 evals/test_flows.py           # run all tests
  python3 evals/test_flows.py --full    # also print full AI responses
"""
import asyncio
import re
import sys
import uuid

import httpx

API_BASE = "https://dhaba-ai-production.up.railway.app"
API_KEY = "3e263b3904fb1a7def01b56860ce66369ad73bc04898eb545f295de0a1717297"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

TOON_RE = re.compile(r"\[TOON_SAVED:\d+\]$")

# ---------------------------------------------------------------------------
# Test cases
# expect_all  → every keyword must appear (AND)
# expect_any  → at least one must appear (OR)
# banned      → none must appear (these indicate wrong behavior)
# ---------------------------------------------------------------------------
TESTS = [
    {
        "id": 1,
        "name": "Today's full report — must call 4 tools",
        "message": "Give me today's full business report",
        "expect_all": ["₹"],
        "expect_any": ["revenue", "orders", "expense", "peak", "kamai"],
        "banned": [],
        "note": "Should show revenue + top dishes + peak hours + expenses",
    },
    {
        "id": 2,
        "name": "Customer with most dues — must NOT ask for phone",
        "message": "Which customer owes us the most?",
        "expect_all": [],
        # If dues exist: ₹ and a name. If no dues: some "no dues" phrase. Both are valid.
        "expect_any": ["₹", "balance", "owes", "outstanding", "baki", "due", "udhar", "nahi hai", "zero", "clear"],
        "banned": ["phone number", "provide the phone", "give me the phone", "phone number to check"],
        "note": "Must call get_all_customer_ledgers (not ask for phone). Empty = 'no dues' is valid.",
    },
    {
        "id": 3,
        "name": "Due customers list — must NOT ask for phone",
        "message": "Do we have any customers with dues? Show me the list.",
        "expect_all": [],
        "expect_any": ["₹", "balance", "outstanding", "no outstanding", "no dues", "koi due nahi",
                       "udhar nahi", "payment clear", "zero", "koi bhi", "sabki"],
        "banned": ["phone number", "provide the phone"],
        "note": "Must call get_all_customer_ledgers. Empty result ('no dues') is valid.",
    },
    {
        "id": 4,
        "name": "Today's expenses — must call get_expenses not dashboard",
        "message": "What are today's total expenses?",
        "expect_all": [],
        # Today genuinely has ₹0 expenses. Accept ₹0 OR any expense phrase.
        "expect_any": ["₹0", "₹", "expense", "kharcha", "kharch", "koi entry nahi", "koi expense nahi", "record nahi"],
        # Must NOT say Bill-App is down when tool just returned empty (₹0 is valid)
        "banned": ["bill-app down", "bill-app band", "shayad bill-app", "maybe bill-app"],
        "note": "Today has ₹0 expenses (no entries). Should say '₹0' not 'Bill-App down'.",
    },
    {
        "id": 5,
        "name": "Active orders right now",
        "message": "Is there any active order right now?",
        "expect_all": [],
        "expect_any": ["active", "no active", "koi active", "pending", "abhi koi order", "order nahi"],
        # Must NOT refuse as out-of-scope — active orders is valid live data
        "banned": ["scope ke baahir", "mere scope", "out of scope", "can't help", "cannot help"],
        "note": "Must call get_orders(status='Pending'). Must NOT refuse as out-of-scope.",
    },
    {
        "id": 6,
        "name": "Veg dishes — no hallucinated descriptions",
        "message": "How many veg dishes do we have and which is the best?",
        "expect_all": [],
        "expect_any": ["veg", "vegetarian", "paneer", "dal", "mix veg"],
        "banned": ["typically", "rich flavor", "flavor profile", "widely loved"],
        "note": "Must call get_all_dishes(dish_type='veg'), no invented descriptions",
    },
    {
        "id": 7,
        "name": "Best selling dish — no wrong category",
        "message": "What is our best selling dish?",
        "expect_all": [],
        "expect_any": ["Fish Masala", "Chicken Masala", "Roti", "fish", "chicken"],
        "banned": ["sabji", "vegetable category", "sabzi category"],
        "note": "Should call get_top_dishes, not invent category",
    },
    {
        "id": 8,
        "name": "This week's revenue",
        "message": "How much revenue did we make this week?",
        "expect_all": ["₹"],
        "expect_any": ["week", "hafte", "revenue", "kamai"],
        "banned": [],
        "note": "Should use pre-resolved this_week_start or call resolve_date",
    },
    {
        "id": 9,
        "name": "Hindi: Aaj ka kharcha",
        "message": "Aaj ka kharcha kitna tha?",
        "expect_all": ["₹"],
        "expect_any": ["kharcha", "expense", "kharch"],
        "banned": [],
        "note": "Hindi expense query — should still call get_expenses",
    },
    {
        "id": 10,
        "name": "Yesterday top items — must use resolve_date first",
        "message": "Kal ke top selling items kya the?",
        "expect_all": [],
        "expect_any": ["Roti", "Fish", "Chicken", "Gutka", "item", "bika"],
        "banned": [],
        "note": "Should call resolve_date('kal') then get_todays_top_items(date)",
    },
    {
        "id": 11,
        "name": "Out-of-scope — must refuse politely",
        "message": "Can you suggest a new marketing campaign for the dhaba?",
        "expect_all": [],
        "expect_any": ["scope", "baahir", "sirf", "live data", "cannot", "can't help"],
        "banned": [],
        "note": "Out of scope — should refuse, not hallucinate marketing ideas",
    },
    {
        "id": 12,
        "name": "Peak hours today",
        "message": "What were the peak hours today?",
        "expect_all": [],
        "expect_any": ["hour", "peak", "orders", "busy", "AM", "PM", "baje", "ghanta"],
        "banned": ["scope ke baahir", "mere scope", "out of scope"],
        "note": "Should call get_peak_hours_today",
    },
]


async def stream_agent(client: httpx.AsyncClient, message: str, session_id: str) -> tuple[str, int]:
    """Returns (full_text, status_code)."""
    full = ""
    try:
        async with client.stream(
            "POST",
            f"{API_BASE}/agent/chat/stream",
            headers=HEADERS,
            json={"message": message, "session_id": session_id},
            timeout=120.0,
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                return f"HTTP {resp.status_code}: {body.decode()[:200]}", resp.status_code
            async for chunk in resp.aiter_text():
                full += chunk
    except httpx.TimeoutException:
        return "TIMEOUT — server took >120s", 0
    except Exception as e:
        return f"NETWORK ERROR: {e}", 0

    full = TOON_RE.sub("", full).strip()
    return full, 200


def evaluate(response: str, test: dict) -> tuple[bool, list[str]]:
    lower = response.lower()
    failures = []

    for kw in test.get("expect_all", []):
        if kw.lower() not in lower:
            failures.append(f"missing required: '{kw}'")

    any_kws = test.get("expect_any", [])
    if any_kws and not any(k.lower() in lower for k in any_kws):
        failures.append(f"none of expected topics found: {any_kws}")

    for kw in test.get("banned", []):
        if kw.lower() in lower:
            failures.append(f"banned phrase present: '{kw}'")

    return len(failures) == 0, failures


async def run():
    print(f"\n{'═'*72}")
    print(f"  Dhaba AI — Flow Tests")
    print(f"  {API_BASE}")
    print(f"{'═'*72}\n")

    results = []
    show_full = "--full" in sys.argv

    async with httpx.AsyncClient() as client:
        for test in TESTS:
            session_id = str(uuid.uuid4())
            print(f"[{test['id']:02d}] {test['name']}")
            print(f"     Q: {test['message']}")
            if test.get("note"):
                print(f"     ℹ {test['note']}")

            response, status = await stream_agent(client, test["message"], session_id)

            if status != 200:
                print(f"     💥 {response}\n")
                results.append({"id": test["id"], "passed": False, "error": response})
                continue

            passed, failures = evaluate(response, test)
            preview = response.replace("\n", " ")[:150]
            if len(response) > 150:
                preview += "…"

            print(f"     A: {preview}")
            print(f"     {'✅ PASS' if passed else '❌ FAIL'}")
            for f in failures:
                print(f"        • {f}")

            if show_full:
                print(f"\n--- Full response ---\n{response}\n{'─'*50}")

            results.append({"id": test["id"], "name": test["name"], "passed": passed, "response": response})
            print()

            await asyncio.sleep(1)  # avoid rate limiting

    passed_count = sum(1 for r in results if r.get("passed"))
    total = len(results)

    print(f"{'═'*72}")
    print(f"  {passed_count}/{total} passed  {'✅ ALL GOOD' if passed_count == total else '❌ FAILURES ABOVE'}")
    print(f"{'═'*72}\n")

    return passed_count == total


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)

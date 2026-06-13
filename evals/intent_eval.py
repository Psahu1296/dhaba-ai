"""Intent-classification eval — the top of the funnel, measured in isolation.

If intent is wrong, the planner runs the wrong tools and every downstream stage
is wrong. This is the fastest loop for tuning intent.py / intent_rules.py: it
hits ONLY the classifier (no Bill-App, no synthesis), so it runs in seconds.

Run: python3 -m evals.intent_eval
Exits 0 if accuracy == 100%, else 1 (CI-friendly).
"""
import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.intent import classify_intent

# (query, expected_intent). Mines the tricky boundaries the few-shots target.
CASES = [
    ("aaj kitna hua?", "revenue"),
    ("is hafte ka revenue?", "revenue"),
    ("kitna kamaya?", "revenue"),
    ("kaisa raha aaj?", "daily_report"),
    ("good day or slow day?", "daily_report"),
    ("was today busy?", "daily_report"),
    ("give me today's full report", "daily_report"),
    ("kal kaisa raha?", "past_report"),
    ("give me yesterday's report", "past_report"),
    ("kal ke top items?", "todays_items"),
    ("what sold 2 days ago?", "todays_items"),
    ("best selling dishes?", "top_dishes"),
    ("most popular dish overall?", "top_dishes"),
    ("kharcha kitna hua?", "expenses"),
    ("expenses this week?", "expenses"),
    ("busiest hours today?", "peak_hours"),
    ("rush time kab tha?", "peak_hours"),
    ("who owes us money?", "customer_dues"),
    ("customers with dues?", "customer_dues"),
    ("balance of 9876543210?", "customer_balance"),
    ("show me the menu", "menu"),
    ("veg dishes under 50?", "menu"),
    ("sabse mehenga dish?", "menu"),
    ("what dal dishes do you serve?", "menu"),
    ("chai serve karte ho?", "consumables"),
    ("gutka kitna bika?", "consumables"),
    ("what drinks or beverages do you serve?", "consumables"),
    ("order list dikhao", "orders"),
    ("is mahine trend kaisa hai?", "historical_trend"),
    ("compare this week to last week", "historical_trend"),
    ("hello", "general"),
    ("thanks bhai", "general"),
    ("what about the second one?", "general"),
    ("tell me more about that", "general"),
]


async def run():
    print(f"Classifying {len(CASES)} queries...\n")
    correct = 0
    confusion = defaultdict(lambda: defaultdict(int))
    misses = []

    for query, expected in CASES:
        result = await classify_intent({"query": query})
        got = result["intent"]["intent"]
        conf = result["intent"]["confidence"]
        confusion[expected][got] += 1
        if got == expected:
            correct += 1
            mark = "✅"
        else:
            mark = "❌"
            misses.append((query, expected, got, conf))
        print(f"{mark} {query:38} exp={expected:17} got={got:17} ({conf:.2f})")

    acc = correct / len(CASES)
    print(f"\n{'─' * 80}")
    print(f"Intent accuracy: {correct}/{len(CASES)} = {acc:.0%}")

    if misses:
        print("\nMisclassifications (candidates for new few-shots):")
        for q, exp, got, conf in misses:
            print(f"  {q!r}  expected {exp}, got {got} ({conf:.2f})")

    sys.exit(0 if correct == len(CASES) else 1)


if __name__ == "__main__":
    asyncio.run(run())

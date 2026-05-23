from pipeline.planner import plan_workflow

cases = [
    {"intent": {"intent": "daily_report",   "date_hint": "today", "phone": None, "confidence": 1.0},  "query": "give me today full report"},
    {"intent": {"intent": "expenses",       "date_hint": "kal",   "phone": None, "confidence": 1.0},  "query": "kal ke expenses"},
    {"intent": {"intent": "revenue",        "date_hint": "aaj",   "phone": None, "confidence": 0.95}, "query": "aaj kitna hua?"},
    {"intent": {"intent": "customer_dues",  "date_hint": None,    "phone": None, "confidence": 0.95}, "query": "who owes us the most?"},
    {"intent": {"intent": "customer_balance","date_hint": None,   "phone": "9876543210", "confidence": 0.9}, "query": "9876543210 ka balance"},
]

for tc in cases:
    state = {**tc, "role": "admin", "plan": None, "raw_results": None, "verified": None, "response": None, "messages": []}
    result = plan_workflow(state)
    print(f"\n[{tc['intent']['intent']}] {tc['query']!r}")
    for s in result["plan"]["steps"]:
        print(f"  → {s['tool_name']}({s['args']})")

from datetime import date, timedelta
import re
from pipeline.state import PipelineState, ExecutionPlan, ToolStep, IntentResult
from tools.processors import detect_period


def _resolve_date(hint: str | None) -> dict:
    """Maps a date hint string to concrete YYYY-MM-DD dates."""
    today = date.today()
    if not hint:
        return {"date": today.isoformat()}

    h = hint.lower().strip()

    single_offsets = {
        "today": 0, "aaj": 0, "abhi": 0,
        "yesterday": 1, "kal": 1, "kal ka": 1,
        "day before yesterday": 2, "parso": 2,
    }
    for key, days in single_offsets.items():
        if h == key:
            return {"date": (today - timedelta(days=days)).isoformat()}

    m = re.match(r'(\d+)\s*(?:days?\s*ago|din\s*pehle)', h)
    if m:
        return {"date": (today - timedelta(days=int(m.group(1)))).isoformat()}

    if h in ("this week", "is hafte", "is week"):
        start = today - timedelta(days=today.weekday())
        return {"from": start.isoformat(), "to": today.isoformat()}

    if h in ("last week", "pichle hafte"):
        start = today - timedelta(days=today.weekday() + 7)
        return {"from": start.isoformat(), "to": (start + timedelta(days=6)).isoformat()}

    if h in ("this month", "is mahine", "is month"):
        return {"from": today.replace(day=1).isoformat(), "to": today.isoformat()}

    if h in ("last month", "pichle mahine"):
        end = today.replace(day=1) - timedelta(days=1)
        return {"from": end.replace(day=1).isoformat(), "to": end.isoformat()}

    return {"date": today.isoformat()}


def plan_workflow(state: PipelineState) -> dict:
    intent: IntentResult = state["intent"]
    name = intent["intent"]
    hint = intent.get("date_hint")
    phone = intent.get("phone")
    query = state["query"]

    today = date.today().isoformat()
    dates = _resolve_date(hint)
    single_date = dates.get("date", today)
    from_date = dates.get("from", single_date)
    to_date = dates.get("to", single_date)

    steps: list[ToolStep] = []

    if name == "daily_report":
        steps = [
            {"tool_name": "get_dashboard_kpis",   "args": {}},
            {"tool_name": "get_todays_top_items",  "args": {"date": today}},
            {"tool_name": "get_peak_hours_today",  "args": {"date": today}},
            {"tool_name": "get_expenses",          "args": {"from_date": today, "to_date": today}},
        ]

    elif name == "past_report":
        steps = [
            {"tool_name": "get_daily_summary", "args": {"date": single_date}},
        ]

    elif name == "revenue":
        period = intent.get("period") or detect_period(hint, query)
        if period in ("today", "week", "month", "year"):
            # KPI dashboard has all four pre-computed — no array scanning needed
            steps = [{"tool_name": "get_dashboard_kpis", "args": {"_period": period}}]
        else:
            # specific past date (e.g. "yesterday", "3 days ago") → history
            steps = [{"tool_name": "get_earnings_history", "args": {"period": "day", "num_periods": 31}}]

    elif name == "expenses":
        steps = [{"tool_name": "get_expenses", "args": {"from_date": from_date, "to_date": to_date}}]

    elif name == "top_dishes":
        steps = [{"tool_name": "get_top_dishes", "args": {"limit": 5}}]

    elif name == "todays_items":
        steps = [{"tool_name": "get_todays_top_items", "args": {"date": single_date}}]

    elif name == "peak_hours":
        steps = [{"tool_name": "get_peak_hours_today", "args": {"date": single_date}}]

    elif name == "customer_dues":
        steps = [{"tool_name": "get_all_customer_ledgers", "args": {}}]

    elif name == "customer_balance":
        steps = [{"tool_name": "get_customer_balance", "args": {"phone": phone or ""}}]

    elif name == "orders":
        steps = [{"tool_name": "get_orders", "args": {"date": single_date}}]

    elif name == "menu":
        cat   = intent.get("category_filter", "")
        steps = [{"tool_name": "get_all_dishes", "args": {
            "dish_type": cat if cat in ("veg", "non-veg") else None,
            "search":    intent.get("search_term"),
            "min_price": intent.get("min_price"),
            "max_price": intent.get("max_price"),
        }}]

    elif name == "consumables":
        steps = [{"tool_name": "get_consumables_summary", "args": {"date": single_date}}]

    elif name == "historical_trend":
        steps = [
            {"tool_name": "search_daily_history", "args": {"query": query}},
            {"tool_name": "get_earnings_range",    "args": {"from_date": from_date, "to_date": to_date}},
        ]

    # "general" → empty steps, synthesizer handles without any tool data

    return {"plan": ExecutionPlan(steps=steps)}

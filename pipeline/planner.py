from pipeline.state import PipelineState, ExecutionPlan, ToolStep, IntentResult
from tools.processors import detect_period
from tools.dates import resolve_day, resolve_range, today_ist


def _resolve_date(hint: str | None) -> dict:
    """Maps a date hint to concrete YYYY-MM-DD dates, resolved against IST.

    Delegates to tools.dates so the pipeline shares the single, timezone-correct
    resolver. Bare date.today() here was a bug: Railway runs UTC, so 'today'
    during IST 00:00–05:30 resolved to yesterday.
    """
    if not hint:
        return {"date": today_ist().isoformat()}
    rng = resolve_range(hint)
    if rng:
        return {"from": rng[0], "to": rng[1]}
    return {"date": resolve_day(hint, default_today=True)}


def plan_workflow(state: PipelineState) -> dict:
    intent: IntentResult = state["intent"]
    name = intent["intent"]
    hint = intent.get("date_hint")
    phone = intent.get("phone")
    query = state["query"]

    today = today_ist().isoformat()
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
        if dates.get("date") and dates["date"] != today:
            # Specific past day ("yesterday", "kal", "3 days ago") — report THAT
            # day's revenue, not today's. detect_period defaults to "today", which
            # used to silently swallow a past date_hint and return today instead.
            steps = [{"tool_name": "get_earnings_range",
                      "args": {"from_date": single_date, "to_date": single_date}}]
        elif period in ("today", "week", "month", "year"):
            # KPI dashboard has all four pre-computed — no array scanning needed
            steps = [{"tool_name": "get_dashboard_kpis", "args": {"_period": period}}]
        else:
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

    # Stamp the tool that MUST succeed for this answer to be trustworthy.
    # The verifier blocks the response if this specific tool failed. Computed
    # here (not in the verifier) because only the planner knows which branch it
    # took — e.g. revenue runs get_dashboard_kpis OR get_earnings_history.
    primary = _PRIMARY_TOOL.get(name) or (steps[0]["tool_name"] if steps else None)

    return {"plan": ExecutionPlan(steps=steps), "primary_tool": primary}


# Intent → the single tool whose success the answer depends on. Intents not
# listed (e.g. revenue, which picks its tool at runtime) fall back to the first
# planned step. "general" has no tool and is intentionally absent.
_PRIMARY_TOOL = {
    "daily_report":     "get_dashboard_kpis",
    "past_report":      "get_daily_summary",
    "expenses":         "get_expenses",
    "top_dishes":       "get_top_dishes",
    "todays_items":     "get_todays_top_items",
    "peak_hours":       "get_peak_hours_today",
    "customer_dues":    "get_all_customer_ledgers",
    "customer_balance": "get_customer_balance",
    "orders":           "get_orders",
    "menu":             "get_all_dishes",
    "consumables":      "get_consumables_summary",
    "historical_trend": "get_earnings_range",
}

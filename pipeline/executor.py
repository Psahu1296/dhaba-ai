import inspect
from tools.bill_app import (
    get_top_dishes,
    get_dashboard_kpis,
    get_expenses,
    get_orders,
    get_customer_balance,
    get_todays_top_items,
    get_peak_hours_today,
    get_earnings_history,
    get_all_customer_ledgers,
    get_consumables_summary,
    get_all_dishes,
    get_daily_summary,
    get_earnings_range,
    get_top_revenue_dishes,
    get_customer_ledger_by_name,
)
from tools.retriever import search_dishes
from tools.daily_embedder import search_daily_summaries
from pipeline.state import PipelineState
from tools.processors import (
    extract_period_revenue, extract_date_revenue,
    find_peak_day, flag_expenses, add_date_label,
    detect_period,
)


_REGISTRY = {
    "get_dashboard_kpis":          lambda a: get_dashboard_kpis(),
    "get_top_dishes":              lambda a: get_top_dishes(a.get("limit", 5)),
    "get_expenses":                lambda a: get_expenses(a.get("from_date"), a.get("to_date")),
    "get_orders":                  lambda a: get_orders(a.get("date"), a.get("status")),
    "get_customer_balance":        lambda a: get_customer_balance(a["phone"]),
    "get_todays_top_items":        lambda a: get_todays_top_items(a.get("limit", 10), a.get("date")),
    "get_peak_hours_today":        lambda a: get_peak_hours_today(a.get("date")),
    "get_earnings_history":        lambda a: get_earnings_history(a.get("period", "day"), a.get("num_periods", 7)),
    "get_all_customer_ledgers":    lambda a: get_all_customer_ledgers(a.get("status")),
    "get_consumables_summary":     lambda a: get_consumables_summary(a.get("date")),
    "get_all_dishes":              lambda a: get_all_dishes(
                                       dish_type=a.get("dish_type"),
                                       category=a.get("category"),
                                       search=a.get("search"),
                                       min_price=a.get("min_price"),
                                       max_price=a.get("max_price"),
                                   ),
    "get_daily_summary":           lambda a: get_daily_summary(a["date"]),
    "get_earnings_range":          lambda a: get_earnings_range(a["from_date"], a["to_date"]),
    "get_top_revenue_dishes":      lambda a: get_top_revenue_dishes(
                                       a.get("limit", 10), a.get("from_date"), a.get("to_date")
                                   ),
    "get_customer_ledger_by_name": lambda a: get_customer_ledger_by_name(a["name"]),
    "search_dishes":               lambda a: search_dishes(a["query"], a.get("n_results", 4)),
    "search_daily_history":        lambda a: search_daily_summaries(a["query"], n_results=5),
}


def _post_process(state: PipelineState, results: dict) -> dict:
    """
    Apply Python transformations after tools run.
    LLM receives clean, labelled, pre-filtered data — no scanning or math needed.
    """
    intent = state["intent"]
    name = intent["intent"]
    query = state.get("query", "")
    hint = intent.get("date_hint")

    if name == "revenue":
        if "get_dashboard_kpis" in results:
            period = intent.get("period") or detect_period(hint, query)
            results["get_dashboard_kpis"] = extract_period_revenue(results["get_dashboard_kpis"], period)
        elif "get_earnings_history" in results:
            # past specific date — pull just that day's entry
            target = state["plan"]["steps"][0]["args"].get("target_date", "")
            if target:
                results["get_earnings_history"] = extract_date_revenue(results["get_earnings_history"], target)

    elif name == "historical_trend" and "get_earnings_range" in results:
        _peak_signals = ("highest", "best day", "peak day", "which day", "konsa din", "most revenue")
        if any(s in query.lower() for s in _peak_signals):
            results["get_earnings_range"] = find_peak_day(results["get_earnings_range"])

    elif name == "menu" and "get_all_dishes" in results:
        _exp_signals = ("expensive", "costly", "mehenga", "mehnga", "sabse mehenga", "highest price", "most expensive")
        _chp_signals = ("cheapest", "sasta", "sabse sasta", "lowest price", "cheapest dish", "least expensive")
        dishes = results["get_all_dishes"]
        if isinstance(dishes, list) and dishes:
            if any(s in query.lower() for s in _exp_signals):
                def _max_price(d):
                    variants = d.get("variants") or []
                    prices = [v.get("price", 0) for v in variants if isinstance(v, dict)]
                    return max(prices) if prices else 0
                top = max(dishes, key=_max_price)
                results["get_all_dishes"] = {
                    "most_expensive_dish": top.get("name"),
                    "price": _max_price(top),
                    "category": top.get("dish_type") or top.get("category"),
                    "variants": top.get("variants", []),
                }
            elif any(s in query.lower() for s in _chp_signals):
                def _min_price(d):
                    variants = d.get("variants") or []
                    prices = [v.get("price", 0) for v in variants if isinstance(v, dict) and v.get("price", 0) > 0]
                    return min(prices) if prices else float("inf")
                bottom = min(dishes, key=_min_price)
                results["get_all_dishes"] = {
                    "cheapest_dish": bottom.get("name"),
                    "price": _min_price(bottom),
                    "category": bottom.get("dish_type") or bottom.get("category"),
                    "variants": bottom.get("variants", []),
                }

    elif name == "expenses" and "get_expenses" in results:
        results["get_expenses"] = flag_expenses(results["get_expenses"])

    # Add date_label to any result that carries a "date" field
    for tool_name, data in results.items():
        if isinstance(data, dict) and "date" in data and "date_label" not in data:
            results[tool_name] = add_date_label(data, data["date"])

    return results


async def execute_tools(state: PipelineState) -> dict:
    plan = state["plan"]
    results = {}
    errors = {}

    for step in plan["steps"]:
        tool_name = step["tool_name"]
        args = step["args"]
        try:
            fn = _REGISTRY.get(tool_name)
            if fn is None:
                errors[tool_name] = f"Unknown tool: {tool_name}"
                continue
            raw = fn(args)
            results[tool_name] = await raw if inspect.isawaitable(raw) else raw
        except Exception as e:
            errors[tool_name] = str(e)

    results = _post_process(state, results)
    return {"raw_results": {"results": results, "errors": errors}}

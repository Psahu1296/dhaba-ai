# stage 4
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
)
from tools.retriever import search_dishes
from tools.daily_embedder import search_daily_summaries
from pipeline.state import PipelineState


_REGISTRY = {
    "get_dashboard_kpis":       lambda a: get_dashboard_kpis(),
    "get_top_dishes":           lambda a: get_top_dishes(a.get("limit", 5)),
    "get_expenses":             lambda a: get_expenses(a.get("from_date"), a.get("to_date")),
    "get_orders":               lambda a: get_orders(a.get("date"), a.get("status")),
    "get_customer_balance":     lambda a: get_customer_balance(a["phone"]),
    "get_todays_top_items":     lambda a: get_todays_top_items(a.get("limit", 10), a.get("date")),
    "get_peak_hours_today":     lambda a: get_peak_hours_today(a.get("date")),
    "get_earnings_history":     lambda a: get_earnings_history(a.get("period", "day"), a.get("num_periods", 7)),
    "get_all_customer_ledgers": lambda a: get_all_customer_ledgers(a.get("status")),
    "get_consumables_summary":  lambda a: get_consumables_summary(a.get("date")),
    "get_all_dishes":           lambda a: get_all_dishes(),
    "search_dishes":            lambda a: search_dishes(a["query"], a.get("n_results", 4)),
    "search_daily_history":     lambda a: search_daily_summaries(a["query"], n_results=5),
}


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

    return {"raw_results": {"results": results, "errors": errors}}

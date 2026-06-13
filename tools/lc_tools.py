from langchain_core.tools import tool
from tools import codec
from datetime import date as _date, timedelta as _timedelta
import re as _re
from tools.bill_app import (
    get_top_dishes as _top_dishes,
    get_dashboard_kpis as _kpis,
    get_revenue as _revenue,
    get_expenses as _expenses,
    get_orders as _orders,
    get_customer_balance as _balance,
    get_todays_top_items as _todays_items,
    get_peak_hours_today as _peak_hours,
    get_earnings_history as _earnings_history,
    get_all_customer_ledgers as _all_ledgers,
    get_consumables_summary as _consumables_summary,
    get_all_dishes as _all_dishes,
    get_daily_summary as _daily_summary,
    get_earnings_range as _earnings_range,
    get_top_revenue_dishes as _top_revenue_dishes,
    get_customer_ledger_by_name as _ledger_by_name,
)
from tools.retriever import search_dishes as _search
from tools.daily_embedder import search_daily_summaries as _search_daily


@tool
def resolve_date(relative: str) -> str:
    """Convert a relative time expression to concrete YYYY-MM-DD dates.
    Call before any data tool when the user uses relative time (kal, yesterday, last week, etc.).
    Returns: {"date": "YYYY-MM-DD"} for a single day, {"from": ..., "to": ...} for a range.
    relative: the exact time phrase from the user."""
    import json
    today = _date.today()
    rel = relative.lower().strip()

    single = {
        "today": 0, "aaj": 0, "abhi": 0,
        "yesterday": 1, "kal": 1, "kal ka": 1,
        "day before yesterday": 2, "parso": 2,
    }
    for key, days in single.items():
        if rel == key:
            d = today - _timedelta(days=days)
            return json.dumps({"date": d.isoformat()})

    m = _re.match(r'(\d+)\s*(?:days?\s*ago|din\s*pehle)', rel)
    if m:
        d = today - _timedelta(days=int(m.group(1)))
        return json.dumps({"date": d.isoformat()})

    if rel in ("this week", "is hafte", "is week"):
        start = today - _timedelta(days=today.weekday())
        return json.dumps({"from": start.isoformat(), "to": today.isoformat()})

    if rel in ("last week", "pichle hafte"):
        start = today - _timedelta(days=today.weekday() + 7)
        end = start + _timedelta(days=6)
        return json.dumps({"from": start.isoformat(), "to": end.isoformat()})

    if rel in ("this month", "is mahine", "is month"):
        start = today.replace(day=1)
        return json.dumps({"from": start.isoformat(), "to": today.isoformat()})

    if rel in ("last month", "pichle mahine"):
        end = today.replace(day=1) - _timedelta(days=1)
        start = end.replace(day=1)
        return json.dumps({"from": start.isoformat(), "to": end.isoformat()})

    return json.dumps({"date": today.isoformat(), "note": f"Could not parse '{relative}', defaulted to today"})


@tool
async def get_top_dishes(limit: int = 5) -> str:
    """All-time cumulative bestsellers since the dhaba opened.
    NOT for what sold on a specific date — use get_todays_top_items for that.
    limit: how many top dishes to return (default 5)."""
    result = await _top_dishes(limit)
    return codec.encode_tool_result("get_top_dishes", result)


@tool
async def get_dashboard_kpis() -> str:
    """Live revenue snapshot: today, this week, this month, this year — each with % change vs previous period.
    NOT for past dates or specific historical days — use get_earnings_history for that."""
    result = await _kpis()
    return codec.encode_tool_result("get_dashboard_kpis", result)


@tool
async def get_expenses(from_date: str = None, to_date: str = None) -> str:
    """Expense records with total for a date range.
    from_date, to_date: YYYY-MM-DD. Use resolve_date first for relative terms.
    Omit both for all-time expenses."""
    result = await _expenses(from_date, to_date)
    return codec.encode_tool_result("get_expenses", result)


@tool
async def get_orders(date: str = None, status: str = None) -> str:
    """Raw order list — individual orders with items, amounts, table, payment status.
    date: YYYY-MM-DD. Use resolve_date first for relative terms.
    status: "Completed" or "Pending". Omit for all orders."""
    result = await _orders(date, status)
    return codec.encode_tool_result("get_orders", result)


@tool
async def get_customer_balance(phone: str) -> str:
    """Outstanding balance for one specific customer by phone number.
    phone: required. For ALL customers with dues — use get_all_customer_ledgers instead."""
    result = await _balance(phone)
    return codec.encode_tool_result("get_customer_balance", result)


@tool
async def search_dishes(query: str, n_results: int = 4) -> str:
    """Semantic search for a dish by name, ingredient, or description.
    NOT for listing all veg/non-veg or filtering by price — use get_all_dishes for that.
    query: dish name, ingredient, or description in any language."""
    result = await _search(query, n_results)
    return codec.encode_tool_result("search_dishes", result)


@tool
async def get_todays_top_items(limit: int = 10, date: str = None) -> str:
    """Top selling items by quantity on a specific date.
    date: YYYY-MM-DD. Use resolve_date first for relative terms.
    NOT for all-time bestsellers — use get_top_dishes for that."""
    result = await _todays_items(limit, date)
    return codec.encode_tool_result("get_todays_top_items", result)


@tool
async def get_peak_hours_today(date: str = None) -> str:
    """Peak ordering hours on a specific date — when was it busiest and order count per hour.
    date: YYYY-MM-DD. Use resolve_date first for relative terms."""
    result = await _peak_hours(date)
    return codec.encode_tool_result("get_peak_hours_today", result)


@tool
async def get_earnings_history(period: str = "day", num_periods: int = 7) -> str:
    """Revenue time series for trend analysis — best/worst days, week-over-week comparison, monthly patterns.
    period: 'day' (default), 'week', 'month', 'year'. num_periods: how far back.
    NOT for a single specific past date — use get_daily_summary for that.
    NOT for current totals (today/week/month) — use get_dashboard_kpis for those."""
    result = await _earnings_history(period, num_periods)
    return codec.encode_tool_result("get_earnings_history", result)


@tool
async def get_all_customer_ledgers(status: str = None) -> str:
    """All customers with outstanding balances, sorted by amount owed, with grand total.
    Call when asked about customer dues WITHOUT a specific phone number.
    NEVER ask for a phone number — this returns all customers at once.
    status: filter if needed. Omit for all customers with any balance."""
    result = await _all_ledgers(status)
    return codec.encode_tool_result("get_all_customer_ledgers", result)


@tool
async def get_consumables_summary(date: str = None) -> str:
    """Daily breakdown of chai, gutka, and cigarette usage — sold, consumed by staff, wasted.
    date: YYYY-MM-DD. Use resolve_date first for relative terms."""
    result = await _consumables_summary(date)
    return codec.encode_tool_result("get_consumables_summary", result)


@tool
async def get_all_dishes(
    dish_type: str = None,
    category: str = None,
    search: str = None,
    min_price: float = None,
    max_price: float = None,
) -> str:
    """Full dish menu with optional server-side filtering.
    dish_type: 'veg' or 'non-veg'. category: 'roti', 'drinks', 'snacks', 'rice', 'sabji', 'other'.
    search: dish name keyword. min_price / max_price: price range in ₹.
    NOT for finding a specific dish by name/ingredient — use search_dishes for that."""
    dishes = await _all_dishes(dish_type=dish_type, category=category,
                               search=search, min_price=min_price, max_price=max_price)
    return codec.encode_tool_result("get_all_dishes", dishes)


@tool
async def get_daily_summary(date: str) -> str:
    """Full business picture for one specific past date — revenue, orders, payment split,
    top items, peak hour, expenses, consumables. All in one call.
    date: YYYY-MM-DD. Use resolve_date first for relative terms like 'kal', 'yesterday'."""
    result = await _daily_summary(date)
    return codec.encode_tool_result("get_daily_summary", result)


@tool
async def get_earnings_range(from_date: str, to_date: str) -> str:
    """Revenue per day for an arbitrary date range. Returns [{date, revenue}] array.
    Use for trend queries, monthly totals, or finding best/worst day in a period.
    from_date, to_date: YYYY-MM-DD. Use resolve_date first for relative terms."""
    result = await _earnings_range(from_date, to_date)
    return codec.encode_tool_result("get_earnings_range", result)


@tool
async def get_top_revenue_dishes(limit: int = 10, from_date: str = None, to_date: str = None) -> str:
    """Top dishes ranked by total revenue earned (quantity × price) — NOT by order count.
    Answers 'which dish makes the most money?' — different from get_top_dishes (by volume).
    limit: max results. from_date / to_date: optional date range (YYYY-MM-DD)."""
    result = await _top_revenue_dishes(limit, from_date, to_date)
    return codec.encode_tool_result("get_top_revenue_dishes", result)


@tool
async def get_customer_ledger_by_name(name: str) -> str:
    """Find a customer's outstanding balance by name (not phone number).
    Use when the user says a customer name without providing a phone number.
    name: partial or full customer name — case-insensitive search."""
    result = await _ledger_by_name(name)
    return codec.encode_tool_result("get_customer_ledger_by_name", result)


@tool
def search_daily_history(query: str) -> str:
    """Semantic search across embedded daily business summaries — for patterns spanning weeks/months.
    NOT for a specific date's data — use get_earnings_history or get_todays_top_items for that.
    query: describe what you're looking for in plain language."""
    results = _search_daily(query, n_results=5)
    return codec.encode_tool_result("search_daily_history", {"matches": results})


ALL_TOOLS = [
    resolve_date,
    get_dashboard_kpis,
    get_daily_summary,
    get_todays_top_items,
    get_peak_hours_today,
    get_earnings_history,
    get_earnings_range,
    get_expenses,
    get_orders,
    get_top_dishes,
    get_top_revenue_dishes,
    get_all_dishes,
    search_dishes,
    get_customer_balance,
    get_customer_ledger_by_name,
    get_all_customer_ledgers,
    get_consumables_summary,
    search_daily_history,
]

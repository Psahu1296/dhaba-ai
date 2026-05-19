import json
from langchain_core.tools import tool
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
)
from tools.retriever import search_dishes as _search
from tools.daily_embedder import search_daily_summaries as _search_daily



@tool
async def get_top_dishes(limit: int = 5) -> str:
    """ALL-TIME historical bestsellers only. Do NOT use for today-specific queries. Use get_todays_top_items for what sold today."""
    result = await _top_dishes(limit)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_dashboard_kpis() -> str:
    """Get today's business KPIs — revenue, orders, percentage change."""
    result = await _kpis()
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_revenue(period: str = "day") -> str:
    """Get revenue for a time period. period must be: 'day', 'week', 'month', or 'year'."""
    result = await _revenue(period)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_expenses(from_date: str = None, to_date: str = None) -> str:
    """Get expense records. Optionally filter by from_date and to_date (YYYY-MM-DD)."""
    result = await _expenses(from_date, to_date)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_orders(date: str = None, status: str = None) -> str:
    """Get orders. Optionally filter by date (YYYY-MM-DD) and status (Completed/Pending)."""
    result = await _orders(date, status)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_customer_balance(phone: str) -> str:
    """Get a customer's outstanding balance. Requires phone number."""
    result = await _balance(phone)
    return json.dumps(result, ensure_ascii=False)


@tool
async def search_dishes(query: str, n_results: int = 4) -> str:
    """Semantic search over the full dish menu. Use for menu questions, dietary preferences, price range."""
    result = await _search(query, n_results)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_todays_top_items(limit: int = 10, date: str = None) -> str:
    """Get top selling items for a specific date. date is YYYY-MM-DD, defaults to today.
    Use for: most sold today, top items yesterday, bestsellers on a specific date."""
    result = await _todays_items(limit, date)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_peak_hours_today(date: str = None) -> str:
    """Get peak ordering hours for a specific date. date is YYYY-MM-DD, defaults to today.
    Use for: busiest time today, peak hours yesterday, when most orders came on a date."""
    result = await _peak_hours(date)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_earnings_history(period: str = "day", num_periods: int = 7) -> str:
    """Get earnings over multiple periods as a time series.
    period: 'day', 'week', 'month', 'year'. num_periods: how many periods back.
    Use for: revenue trends, best/worst week, slowest month, historical performance comparison."""
    result = await _earnings_history(period, num_periods)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_all_customer_ledgers(status: str = None) -> str:
    """Get all customer credit/balance records. status filter: 'pending' for unpaid dues only.
    Use for: who owes us money, total outstanding balance, customer dues list."""
    result = await _all_ledgers(status)
    return json.dumps(result, ensure_ascii=False)


@tool
async def get_consumables_summary(date: str = None) -> str:
    """Get daily tea/gutka/cigarette usage breakdown. date is YYYY-MM-DD, defaults to today.
    Shows sold to customers, staff consumed, wasted. Use for: inventory tracking, consumable costs."""
    result = await _consumables_summary(date)
    return json.dumps(result, ensure_ascii=False)

@tool
def search_daily_history(query: str) -> str:
    """Search historical daily summaries. Use for: best/worst day patterns,
    trends over weeks, which day had most orders, slowest period last month."""
    results = _search_daily(query, n_results=5)
    return json.dumps({"matches": results}, ensure_ascii=False)

ALL_TOOLS = [
    get_top_dishes,
    get_dashboard_kpis,
    get_revenue,
    get_expenses,
    get_orders,
    get_customer_balance,
    search_dishes,
    get_todays_top_items,
    get_peak_hours_today,
    get_earnings_history,
    get_all_customer_ledgers,
    get_consumables_summary,
    search_daily_history,
]


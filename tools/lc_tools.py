from langchain_core.tools import tool
from tools import codec
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
)
from tools.retriever import search_dishes as _search
from tools.daily_embedder import search_daily_summaries as _search_daily


@tool
async def get_top_dishes(limit: int = 5) -> str:
    """ALL-TIME historical bestsellers only. Do NOT use for today-specific queries. Use get_todays_top_items for what sold today."""
    result = await _top_dishes(limit)
    return codec.encode_tool_result("get_top_dishes", result)


@tool
async def get_dashboard_kpis() -> str:
    """Get revenue totals for ALL periods: today, this week, this month, this year — plus % change vs previous period.
    Use this for ANY revenue question: how much today, this week, this month, this year.
    This is the ONLY accurate revenue source — do not use get_revenue or get_earnings_history for current period totals."""
    result = await _kpis()
    return codec.encode_tool_result("get_dashboard_kpis", result)


@tool
async def get_revenue(period: str = "day") -> str:
    """Get revenue for a time period. period must be: 'day', 'week', 'month', or 'year'."""
    result = await _revenue(period)
    return codec.encode_tool_result("get_revenue", result)


@tool
async def get_expenses(from_date: str = None, to_date: str = None) -> str:
    """Get expense records with total pre-computed. Optionally filter by from_date and to_date (YYYY-MM-DD)."""
    result = await _expenses(from_date, to_date)
    return codec.encode_tool_result("get_expenses", result)


@tool
async def get_orders(date: str = None, status: str = None) -> str:
    """Get orders. Optionally filter by date (YYYY-MM-DD) and status (Completed/Pending)."""
    result = await _orders(date, status)
    return codec.encode_tool_result("get_orders", result)


@tool
async def get_customer_balance(phone: str) -> str:
    """Get a customer's outstanding balance. Requires phone number."""
    result = await _balance(phone)
    return codec.encode_tool_result("get_customer_balance", result)


@tool
async def search_dishes(query: str, n_results: int = 4) -> str:
    """Semantic search for a specific dish by name, flavor, or ingredient.
    NOT for listing veg/non-veg or filtering by price — use get_all_dishes for that."""
    result = await _search(query, n_results)
    return codec.encode_tool_result("search_dishes", result)


@tool
async def get_todays_top_items(limit: int = 10, date: str = None) -> str:
    """Get top selling items for a specific date. date is YYYY-MM-DD, defaults to today.
    Use for: most sold today, top items yesterday, bestsellers on a specific date."""
    result = await _todays_items(limit, date)
    return codec.encode_tool_result("get_todays_top_items", result)


@tool
async def get_peak_hours_today(date: str = None) -> str:
    """Get peak ordering hours for a specific date. date is YYYY-MM-DD, defaults to today.
    Use for: busiest time today, peak hours yesterday, when most orders came on a date."""
    result = await _peak_hours(date)
    return codec.encode_tool_result("get_peak_hours_today", result)


@tool
async def get_earnings_history(period: str = "day", num_periods: int = 7) -> str:
    """Get historical earnings trend as a time series — best/worst periods pre-identified.
    period: 'day', 'week', 'month', 'year'. num_periods: how many periods back (default 7).
    Use ONLY for: trends over time, best/worst week ever, comparing multiple past months.
    Do NOT use for current period totals — use get_dashboard_kpis for that."""
    result = await _earnings_history(period, num_periods)
    return codec.encode_tool_result("get_earnings_history", result)


@tool
async def get_all_customer_ledgers(status: str = None) -> str:
    """Get all customer balance records sorted by balance_due descending (highest first), with total outstanding pre-computed.
    Use for: who owes the most, total outstanding dues, full customer credit list."""
    result = await _all_ledgers(status)
    return codec.encode_tool_result("get_all_customer_ledgers", result)


@tool
async def get_consumables_summary(date: str = None) -> str:
    """Get daily tea/gutka/cigarette usage breakdown. date is YYYY-MM-DD, defaults to today.
    Shows sold to customers, staff consumed, wasted. Use for: inventory tracking, consumable costs."""
    result = await _consumables_summary(date)
    return codec.encode_tool_result("get_consumables_summary", result)


@tool
async def get_all_dishes(dish_type: str = None, max_price: float = None) -> str:
    """Get the dish menu. Optionally filter before returning.
    dish_type: 'veg' or 'non-veg'. max_price: only dishes with any variant priced at or below this.
    Use for: listing veg dishes, non-veg dishes, full menu, price-based filtering.
    Do NOT use search_dishes for listing/filtering — always use this tool."""
    import json as _json
    dishes = await _all_dishes()

    if dish_type:
        dishes = [d for d in dishes if d.get("type", "").lower() == dish_type.lower()]

    if max_price is not None:
        def _parse_variants(dish):
            v = dish.get("variants", [])
            if isinstance(v, str):
                try:
                    v = _json.loads(v)
                except Exception:
                    return []
            return v if isinstance(v, list) else []

        def _under_price(dish):
            for v in _parse_variants(dish):
                try:
                    price = float(str(v.get("price", 9999)).replace("₹", "").replace(",", "").strip())
                    if price <= max_price:
                        return True
                except (ValueError, TypeError):
                    pass
            return False

        dishes = [d for d in dishes if _under_price(d)]

    return codec.encode_tool_result("get_all_dishes", dishes)


@tool
def search_daily_history(query: str) -> str:
    """Search historical daily summaries. Use for: best/worst day patterns,
    trends over weeks, which day had most orders, slowest period last month."""
    results = _search_daily(query, n_results=5)
    return codec.encode_tool_result("search_daily_history", {"matches": results})


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
    get_all_dishes,
    search_daily_history,
]

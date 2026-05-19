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
    get_all_dishes as _all_dishes,
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
    """Get expense records with total pre-computed. Optionally filter by from_date and to_date (YYYY-MM-DD)."""
    result = await _expenses(from_date, to_date)
    records = result if isinstance(result, list) else result.get("data", [])
    total = sum(float(e.get("amount", 0)) for e in records)
    return json.dumps({"total": total, "count": len(records), "expenses": records}, ensure_ascii=False)


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
    """Semantic search for a specific dish by name, flavor, or ingredient.
    NOT for listing veg/non-veg or filtering by price — use get_all_dishes for that."""
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
    """Get earnings over multiple periods as a time series with best/worst period pre-identified.
    period: 'day', 'week', 'month', 'year'. num_periods: how many periods back.
    Use for: revenue trends, best/worst week, slowest month, historical performance comparison."""
    result = await _earnings_history(period, num_periods)
    periods = result if isinstance(result, list) else result.get("data", [])

    if periods:
        def _earnings(p: dict) -> float:
            return float(p.get("total_earnings", p.get("earnings", p.get("amount", 0))))

        sorted_p = sorted(periods, key=_earnings, reverse=True)
        best = sorted_p[0]
        worst = sorted_p[-1]
        return json.dumps({
            "periods": periods,
            "best_period": best,
            "worst_period": worst,
        }, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False)


@tool
async def get_all_customer_ledgers(status: str = None) -> str:
    """Get all customer balance records sorted by balance_due descending (highest first), with total outstanding pre-computed.
    Use for: who owes the most, total outstanding dues, full customer credit list."""
    result = await _all_ledgers(status)
    records = result if isinstance(result, list) else result.get("data", [])
    records.sort(key=lambda x: float(x.get("balance_due", 0)), reverse=True)
    total_outstanding = sum(float(r.get("balance_due", 0)) for r in records)
    return json.dumps({"total_outstanding": total_outstanding, "customers": records}, ensure_ascii=False)


@tool
async def get_consumables_summary(date: str = None) -> str:
    """Get daily tea/gutka/cigarette usage breakdown. date is YYYY-MM-DD, defaults to today.
    Shows sold to customers, staff consumed, wasted. Use for: inventory tracking, consumable costs."""
    result = await _consumables_summary(date)
    return json.dumps(result, ensure_ascii=False)

@tool
async def get_all_dishes(dish_type: str = None, max_price: float = None) -> str:
    """Get the dish menu. Optionally filter before returning.
    dish_type: 'veg' or 'non-veg'. max_price: only dishes with any variant priced at or below this.
    Use for: listing veg dishes, non-veg dishes, full menu, price-based filtering.
    Do NOT use search_dishes for listing/filtering — always use this tool."""
    dishes = await _all_dishes()

    if dish_type:
        dishes = [d for d in dishes if d.get("type", "").lower() == dish_type.lower()]

    if max_price is not None:
        def _under_price(dish: dict) -> bool:
            variants = dish.get("variants", [])
            if isinstance(variants, str):
                variants = json.loads(variants)
            for v in variants:
                try:
                    price = float(str(v.get("price", 9999)).replace("₹", "").replace(",", "").strip())
                    if price <= max_price:
                        return True
                except (ValueError, TypeError):
                    pass
            return False
        dishes = [d for d in dishes if _under_price(d)]

    return json.dumps(dishes, ensure_ascii=False)


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
    get_all_dishes,
    search_daily_history,
]


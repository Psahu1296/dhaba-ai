import httpx
import logging
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)
from config import BILL_APP_URL, BILL_APP_EMAIL, BILL_APP_PASSWORD

from datetime import date as _date, datetime as _datetime, timedelta as _timedelta
import json as _json
import asyncio
import os
from tools.dates import today_ist
from tools.money import rupees, sum_rupees

_IST_OFFSET = _timedelta(hours=5, minutes=30)


def _utc_to_ist_hour(ts: str) -> int | None:
    """Parse a UTC ISO timestamp and return the IST hour (0-23)."""
    try:
        dt = _datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (dt + _IST_OFFSET).hour
    except Exception:
        return None


def _utc_to_ist_str(ts: str) -> str:
    """Convert UTC ISO timestamp to a readable IST string like '10:32 AM'."""
    try:
        dt = _datetime.fromisoformat(ts.replace("Z", "+00:00"))
        ist = dt + _IST_OFFSET
        hour = ist.hour % 12 or 12
        ampm = "AM" if ist.hour < 12 else "PM"
        return f"{hour}:{ist.minute:02d} {ampm} IST"
    except Exception:
        return ts

logger = logging.getLogger(__name__)

_client = httpx.AsyncClient(base_url=BILL_APP_URL, timeout=30.0)




COOKIE_FILE = ".dev_cookie.json"

async def login() -> None:
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE) as f:
                for name, value in _json.load(f).items():
                    _client.cookies.set(name, value)
            logger.info("Loaded saved Bill-App session from cookie file")
            return
        except Exception:
            pass

    for attempt in range(3):
        try:
            response = await _client.post(
                "/api/user/login",
                json={"email": BILL_APP_EMAIL, "password": BILL_APP_PASSWORD},
            )
            response.raise_for_status()
            with open(COOKIE_FILE, "w") as f:
                _json.dump(dict(_client.cookies), f)
            logger.info("Logged into Bill-App and saved session")
            return
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 30 * (attempt + 1)
                logger.warning(f"Login rate limited. Retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                raise

    # httpx automatically stores Set-Cookie from the response into _client.cookies
    # Same as browser storing httpOnly cookie after login


# Transient transport failures (connection drops, read timeouts) are exactly the
# Railway ↔ Bill-App blips that should be retried, not surfaced to the user.
# HTTP status errors (401/4xx/5xx) are NOT retried here — 401 is handled by the
# re-auth path below, and a 4xx won't fix itself.
_TRANSIENT = (
    httpx.ConnectError, httpx.ConnectTimeout,
    httpx.ReadTimeout, httpx.WriteTimeout,
    httpx.PoolTimeout, httpx.RemoteProtocolError,
)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type(_TRANSIENT),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def _send(method: str, url: str, **kwargs):
    return await _client.request(method, url, **kwargs)


async def _request(method: str, url: str, **kwargs):
    """Auto-refreshes Bill-App session on 401; retries transient network errors."""
    response = await _send(method, url, **kwargs)
    if response.status_code == 401:
        logger.warning("Bill-App session expired — re-authenticating")
        if os.path.exists(COOKIE_FILE):
            os.remove(COOKIE_FILE)
        _client.cookies.clear()
        await login()
        response = await _send(method, url, **kwargs)
    response.raise_for_status()
    return response


async def get_top_dishes(limit: int = 5) -> dict:
    response = await _request("GET", "/api/dishes/frequent", params={"limit": limit})
    return response.json()


async def get_dashboard_kpis() -> dict:
    response = await _request("GET", "/api/earnings/dashboard")
    raw = response.json().get("data", {})
    # Rename fields explicitly so LLM never confuses revenue totals with order counts
    return {
        "today_revenue_rupees": raw.get("daily", {}).get("total", 0),
        "today_vs_yesterday_pct": raw.get("daily", {}).get("percentageChange", 0),
        "week_revenue_rupees": raw.get("weekly", {}).get("total", 0),
        "week_vs_last_week_pct": raw.get("weekly", {}).get("percentageChange", 0),
        "month_revenue_rupees": raw.get("monthly", {}).get("total", 0),
        "month_vs_last_month_pct": raw.get("monthly", {}).get("percentageChange", 0),
        "year_revenue_rupees": raw.get("yearly", {}).get("total", 0),
    }

async def get_orders(date: str = None, status: str = None) -> dict:
    params = {}
    if date:
        params["startDate"] = date
    if status:
        params["orderStatus"] = status
    response = await _request("GET", "/api/order", params=params)
    data = response.json()
    # Add IST time to every order so LLM never has to guess timezone
    orders = data if isinstance(data, list) else data.get("data", data.get("orders", []))
    for order in orders:
        ts = order.get("createdAt", "")
        if ts:
            order["time_ist"] = _utc_to_ist_str(ts)
    return data


async def get_expenses(from_date: str = None, to_date: str = None) -> dict:
    params = {}
    if from_date: params["from"] = from_date
    if to_date:   params["to"]   = to_date
    response = await _request("GET", "/api/expenses", params=params)
    all_expenses = response.json().get("data", [])
    filtered = [{
        "name":          e.get("name"),
        "type":          e.get("type"),
        "amount_rupees": rupees(e.get("amount", 0)),
        "date":          (e.get("expenseDate") or "")[:10],
    } for e in all_expenses]
    total = sum_rupees(e["amount_rupees"] for e in filtered)
    return {
        "expenses":     filtered,
        "total_rupees": total,
        "count":        len(filtered),
        "from":         from_date,
        "to":           to_date,
        "note": "No expenses recorded for this period — ₹0 is valid, not an error." if not filtered else None,
    }


async def get_customer_balance(phone: str) -> dict:
    response = await _request("GET", f"/api/ledger/{phone}")
    return response.json()


async def get_revenue(period: str = "day") -> dict:
    response = await _request("GET", f"/api/earnings/{period}")
    return response.json()


async def get_all_dishes(
    dish_type: str = None,
    category: str = None,
    search: str = None,
    min_price: float = None,
    max_price: float = None,
) -> list:
    params = {}
    if dish_type:  params["type"]     = dish_type
    if category:   params["category"] = category
    if search:     params["search"]   = search
    if min_price:  params["minPrice"] = min_price
    if max_price:  params["maxPrice"] = max_price
    response = await _request("GET", "/api/dishes", params=params)
    return response.json().get("data", [])



async def get_todays_top_items(limit: int = 10, date: str = None) -> dict:
    target = date or today_ist().isoformat()
    data = await get_orders(date=target)
    orders = data if isinstance(data, list) else data.get("data", data.get("orders", []))

    counts = {}
    for order in orders:
        items = order.get("items", [])
        if isinstance(items, str):
            items = _json.loads(items)
        for item in items:
            name = item.get("name") or item.get("dish_name") or "unknown"
            qty = int(item.get("quantity") or item.get("qty") or 1)
            counts[name] = counts.get(name, 0) + qty

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    # First order time in IST (orders come back newest-first from API; sort by createdAt)
    sorted_orders = sorted(orders, key=lambda o: o.get("createdAt", ""))
    first_order_time = sorted_orders[0].get("time_ist", "") if sorted_orders else ""

    return {
        "date": target,
        "top_items": [{"name": n, "quantity": q} for n, q in ranked[:limit]],
        "total_orders": len(orders),
        "first_order_time_ist": first_order_time,
    }


async def get_peak_hours_today(date: str = None) -> dict:
    target = date or today_ist().isoformat()
    data = await get_orders(date=target)
    orders = data if isinstance(data, list) else data.get("data", data.get("orders", []))

    hour_counts = {}
    for order in orders:
        ts = order.get("createdAt") or order.get("created_at") or order.get("time") or ""
        hour = _utc_to_ist_hour(ts)
        if hour is not None:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1

    if not hour_counts:
        return {"date": target, "message": "No timing data available"}

    peak = max(hour_counts, key=hour_counts.get)
    peak_end = (peak + 1) % 24
    return {
        "date": target,
        "peak_hour_ist": f"{peak % 12 or 12}:00 {'AM' if peak < 12 else 'PM'} – {peak_end % 12 or 12}:00 {'AM' if peak_end < 12 else 'PM'} IST",
        "peak_order_count": hour_counts[peak],
        "all_hours_ist": {
            f"{h % 12 or 12}:00 {'AM' if h < 12 else 'PM'}": c
            for h, c in sorted(hour_counts.items())
        },
    }


async def get_earnings_history(period: str = "day", num_periods: int = 7) -> dict:
    response = await _request("GET", f"/api/earnings/{period}", params={"numPeriods": num_periods})
    return response.json()


async def get_all_customer_ledgers(status: str = None) -> dict:
    response = await _request("GET", "/api/ledger/all", params={"hasBalance": "true"})
    customers = response.json().get("data", [])
    with_dues = [{
        "name":              c.get("customerName"),
        "phone":             c.get("customerPhone"),
        "balance_due_rupees": rupees(c.get("balanceDue", 0)),
        "last_activity":     (c.get("lastActivity") or "")[:10],
    } for c in customers]
    return {
        "customers_with_dues":      with_dues,
        "total_outstanding_rupees": sum_rupees(c["balance_due_rupees"] for c in with_dues),
        "count":                    len(with_dues),
    }


async def get_consumables_summary(date: str = None) -> dict:
    params = {}
    if date:
        params["date"] = date
    response = await _request("GET", "/api/consumables/summary/day", params=params)
    return response.json()


async def get_daily_summary(date: str) -> dict:
    try:
        response = await _request("GET", f"/api/daily-summary/{date}")
        data = response.json().get("data", {})
        if data and (data.get("order_count", 0) > 0 or data.get("revenue", 0) > 0):
            return data
    except Exception:
        pass

    # Fallback: compute from orders when daily_earnings table is stale
    orders_data = await get_orders(date=date)
    orders = orders_data if isinstance(orders_data, list) else orders_data.get("data", orders_data.get("orders", []))

    revenue = sum_rupees(o.get("bills", {}).get("total", 0) for o in orders)

    payment_split = {"cash": 0, "upi": 0, "card": 0, "credit": 0}
    for o in orders:
        pm = (o.get("paymentMethod") or "").lower()
        if pm in payment_split:
            payment_split[pm] += 1

    counts = {}
    for order in orders:
        items = order.get("items", [])
        if isinstance(items, str):
            items = _json.loads(items)
        for item in items:
            name = item.get("name") or "unknown"
            qty = int(item.get("quantity") or 1)
            counts[name] = counts.get(name, 0) + qty
    top_items = [
        {"name": n, "quantity": q}
        for n, q in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    expenses_data = await get_expenses(from_date=date, to_date=date)

    return {
        "date": date,
        "revenue": revenue,
        "order_count": len(orders),
        # Pre-computed so the model never does revenue/orders itself (it gets this wrong).
        "avg_order_value": rupees(revenue / len(orders)) if orders else 0,
        "payment_split": payment_split,
        "top_items_by_qty": top_items,
        "expenses_rupees": expenses_data.get("total_rupees", 0),
    }


async def get_daily_summary_range(from_date: str, to_date: str) -> list:
    response = await _request("GET", "/api/daily-summary/range",
                              params={"from": from_date, "to": to_date})
    return response.json().get("data", [])


async def get_earnings_range(from_date: str, to_date: str) -> list:
    response = await _request("GET", "/api/earnings/range",
                              params={"from": from_date, "to": to_date})
    return response.json().get("data", [])


async def get_top_revenue_dishes(limit: int = 10, from_date: str = None, to_date: str = None) -> list:
    params: dict = {"limit": limit}
    if from_date: params["from"] = from_date
    if to_date:   params["to"]   = to_date
    response = await _request("GET", "/api/dishes/top-revenue", params=params)
    return response.json().get("data", [])


async def get_customer_ledger_by_name(name: str) -> dict:
    response = await _request("GET", "/api/ledger/all",
                              params={"search": name, "hasBalance": "true"})
    customers = response.json().get("data", [])
    return {
        "matches": [{
            "name":               c.get("customerName"),
            "phone":              c.get("customerPhone"),
            "balance_due_rupees": c.get("balanceDue", 0),
            "last_activity":      (c.get("lastActivity") or "")[:10],
        } for c in customers],
        "count": len(customers),
    }

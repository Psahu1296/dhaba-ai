import httpx
from config import BILL_APP_URL, BILL_APP_EMAIL, BILL_APP_PASSWORD

from datetime import date as _date
import json as _json
import asyncio
import os

# One shared client for the whole app — holds cookies after login
# JS equivalent: const apiClient = axios.create({ baseURL, withCredentials: true })
_client = httpx.AsyncClient(base_url=BILL_APP_URL)




COOKIE_FILE = ".dev_cookie.json"

async def login() -> None:
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE) as f:
                for name, value in _json.load(f).items():
                    _client.cookies.set(name, value)
            print("✓ Loaded saved session")
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
            print("✓ Logged in and saved session")
            return
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 30 * (attempt + 1)
                print(f"Login rate limited. Retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                raise

    # httpx automatically stores Set-Cookie from the response into _client.cookies
    # Same as browser storing httpOnly cookie after login


async def get_top_dishes(limit: int = 5) -> dict:
    response = await _client.get("/api/dishes/frequent", params={"limit": limit})
    response.raise_for_status()
    return response.json()


async def get_dashboard_kpis() -> dict:
    response = await _client.get("/api/earnings/dashboard")
    response.raise_for_status()
    return response.json()

async def get_orders(date: str = None, status: str = None) -> dict:
    params = {}
    if date:
        params["startDate"] = date
    if status:
        params["orderStatus"] = status
    response = await _client.get("/api/order", params=params)
    response.raise_for_status()
    return response.json()


async def get_expenses(from_date: str = None, to_date: str = None) -> dict:
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    response = await _client.get("/api/expenses", params=params)
    response.raise_for_status()
    return response.json()


async def get_customer_balance(phone: str) -> dict:
    response = await _client.get(f"/api/ledger/{phone}")
    response.raise_for_status()
    return response.json()


async def get_revenue(period: str = "day") -> dict:
    response = await _client.get(f"/api/earnings/{period}")
    response.raise_for_status()
    return response.json()


async def get_all_dishes() -> list:
    response = await _client.get("/api/dishes")
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])



async def get_todays_top_items(limit: int = 10, date: str = None) -> dict:
    target = date or _date.today().isoformat()
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
    return {"date": target, "top_items": [{"name": n, "quantity": q} for n, q in ranked[:limit]]}


async def get_peak_hours_today(date: str = None) -> dict:
    target = date or _date.today().isoformat()
    data = await get_orders(date=target)
    orders = data if isinstance(data, list) else data.get("data", data.get("orders", []))

    hour_counts = {}
    for order in orders:
        ts = order.get("createdAt") or order.get("created_at") or order.get("time") or ""
        try:
            hour = int(ts.split("T")[1][:2]) if "T" in ts else int(ts.split(":")[0][-2:])
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        except (ValueError, IndexError, TypeError):
            continue

    if not hour_counts:
        return {"date": target, "message": "No timing data available"}

    peak = max(hour_counts, key=hour_counts.get)
    return {
        "date": target,
        "peak_hour": f"{peak:02d}:00 – {(peak + 1) % 24:02d}:00",
        "peak_order_count": hour_counts[peak],
        "all_hours": {f"{h:02d}:00": c for h, c in sorted(hour_counts.items())}
    }


async def get_earnings_history(period: str = "day", num_periods: int = 7) -> dict:
    response = await _client.get(f"/api/earnings/{period}", params={"numPeriods": num_periods})
    response.raise_for_status()
    return response.json()


async def get_all_customer_ledgers(status: str = None) -> dict:
    params = {}
    if status:
        params["status"] = status
    response = await _client.get("/api/ledger/all", params=params)
    response.raise_for_status()
    return response.json()


async def get_consumables_summary(date: str = None) -> dict:
    params = {}
    if date:
        params["date"] = date
    response = await _client.get("/api/consumables/summary/day", params=params)
    response.raise_for_status()
    return response.json()

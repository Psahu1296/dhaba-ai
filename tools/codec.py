import json
from toon_format import encode as _encode

# Module-level savings accumulator — not thread-safe, fine for single-user demo
_savings: list[int] = []


def reset():
    _savings.clear()


def total_chars_saved() -> int:
    return sum(_savings)


def to_toon(data) -> str:
    raw = json.dumps(data, ensure_ascii=False)
    toon = str(_encode(_clean(data)))
    _savings.append(max(0, len(raw) - len(toon)))
    return toon


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_clean(i) for i in obj]
    return obj


def encode_tool_result(tool_name: str, result) -> str:
    slim_fn = _SLIM_MAP.get(tool_name)
    data = slim_fn(result) if slim_fn else result
    return to_toon(data)


# ── Slim functions — keep only what the LLM needs ──────────────────────────

def slim_orders(result) -> dict:
    orders = result if isinstance(result, list) else result.get("data", result.get("orders", []))
    return {
        "count": len(orders),
        "orders": [
            {
                "id": o.get("id"),
                "status": o.get("orderStatus") or o.get("status"),
                "amount": o.get("totalAmount") or o.get("total_amount"),
                "table": o.get("table_id"),
                "time": (o.get("createdAt") or o.get("created_at") or "")[:16],
            }
            for o in orders[:50]
        ],
    }


def slim_top_dishes(result) -> list:
    dishes = result if isinstance(result, list) else result.get("data", result.get("dishes", []))
    return [
        {
            "name": d.get("name"),
            "orders": d.get("number_of_orders") or d.get("count"),
            "category": d.get("category"),
        }
        for d in dishes
    ]


def slim_kpis(result: dict) -> dict:
    return {
        "today_earning": result.get("todayEarning") or result.get("today_earning"),
        "pct_change": result.get("percentageChange") or result.get("percentage_change"),
        "order_count": result.get("totalOrders") or result.get("order_count") or result.get("orderCount"),
        "customer_count": result.get("customerCount") or result.get("customer_count"),
    }


def slim_revenue(result: dict) -> dict:
    drop = {"id", "createdAt", "updatedAt", "created_at", "updated_at"}
    return {k: v for k, v in result.items() if k not in drop}


def slim_expenses(result) -> dict:
    records = result if isinstance(result, list) else result.get("data", [])
    total = sum(float(e.get("amount", 0)) for e in records)
    return {
        "total": total,
        "count": len(records),
        "expenses": [
            {
                "amount": e.get("amount"),
                "type": e.get("type") or e.get("expenseType"),
                "date": (e.get("expense_date") or e.get("date") or "")[:10],
            }
            for e in records
        ],
    }


def slim_customer_balance(result: dict) -> dict:
    return {
        "name": result.get("customer_name") or result.get("name"),
        "phone": result.get("customer_phone") or result.get("phone"),
        "balance_due": result.get("balance_due"),
        "last_activity": (result.get("last_activity") or "")[:10],
    }


def slim_customer_ledgers(result) -> dict:
    records = result if isinstance(result, list) else result.get("data", [])
    slim = [
        {
            "name": r.get("customer_name") or r.get("name"),
            "phone": r.get("customer_phone") or r.get("phone"),
            "balance": r.get("balance_due"),
        }
        for r in records
    ]
    slim.sort(key=lambda x: float(x.get("balance") or 0), reverse=True)
    return {
        "total_outstanding": sum(float(r.get("balance") or 0) for r in slim),
        "customers": slim,
    }


def slim_dishes(dishes: list) -> list:
    def _variants(d):
        v = d.get("variants", [])
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                return []
        return v if isinstance(v, list) else []

    return [
        {
            "name": d.get("name"),
            "type": d.get("type"),
            "category": d.get("category"),
            "prices": [v.get("price") for v in _variants(d) if v.get("price") is not None],
        }
        for d in dishes
    ]


def slim_earnings_history(result) -> dict:
    periods = result if isinstance(result, list) else result.get("data", [])
    slim = [
        {
            "date": p.get("date") or p.get("period"),
            "earnings": p.get("total_earnings") or p.get("earnings") or p.get("amount"),
        }
        for p in periods
    ]
    if slim:
        by_earn = sorted(slim, key=lambda x: float(x.get("earnings") or 0), reverse=True)
        return {"periods": slim, "best": by_earn[0], "worst": by_earn[-1]}
    return {"periods": slim}


_SLIM_MAP = {
    "get_orders": slim_orders,
    "get_top_dishes": slim_top_dishes,
    "get_dashboard_kpis": slim_kpis,
    "get_revenue": slim_revenue,
    "get_expenses": slim_expenses,
    "get_customer_balance": slim_customer_balance,
    "get_all_customer_ledgers": slim_customer_ledgers,
    "get_all_dishes": lambda r: slim_dishes(r if isinstance(r, list) else r.get("data", [])),
    "get_earnings_history": slim_earnings_history,
    # already slim — pass through
    "get_todays_top_items": lambda r: r,
    "get_peak_hours_today": lambda r: r,
    "search_dishes": lambda r: r,
    "search_daily_history": lambda r: r,
    "get_consumables_summary": lambda r: r,
}

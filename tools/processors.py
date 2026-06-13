import statistics
from datetime import date as _date, timedelta
from typing import Optional
from tools.dates import today_ist
from tools.money import rupees, sum_rupees


def _date_label(d: _date) -> str:
    today = today_ist()
    if d == today:
        return f"Today ({d.strftime('%d %b %Y')})"
    if d == today - timedelta(days=1):
        return f"Yesterday ({d.strftime('%d %b %Y')})"
    return d.strftime("%d %b %Y")


def _revenue_verdict(daily_avg: float) -> str:
    if daily_avg < 1500:
        return "slow"
    if daily_avg < 2000:
        return "below_average"
    if daily_avg < 4000:
        return "normal"
    if daily_avg < 5000:
        return "good"
    return "strong"


def _unwrap_history(raw) -> list[dict]:
    """Extract the list from Bill-App history response. Real shape: {success, data: [{period, earnings}]}"""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("data", "earnings", "history", "records"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
        # Fallback: first list value in the dict
        for v in raw.values():
            if isinstance(v, list):
                return v
    return []


def _entry_date(entry: dict) -> str:
    """Extract date from a history entry. Real field: 'period'."""
    return (entry.get("period") or entry.get("date") or entry.get("earning_date") or "")[:10]


def _entry_revenue(entry: dict) -> float:
    """Extract revenue from a history entry. Real field: 'earnings'."""
    val = entry.get("earnings") or entry.get("total_earnings") or entry.get("revenue") or 0
    return float(val)


# ─── public API ─────────────────────────────────────────────────────────────

def detect_period(date_hint: Optional[str], query: str) -> str:
    """Infer revenue period from hint + query. Returns 'today'/'week'/'month'/'year'."""
    combined = f"{date_hint or ''} {query}".lower()
    if any(s in combined for s in ("year", "saal", "yearly", "annual", "varshik")):
        return "year"
    if any(s in combined for s in ("month", "mahine", "monthly", "mahina", "this month", "is month")):
        return "month"
    if any(s in combined for s in ("week", "hafte", "weekly", "this week", "is hafte", "7 day")):
        return "week"
    return "today"



def extract_period_revenue(kpis: dict, period: str) -> dict:
    """
    Pull a single period's revenue from dashboard KPIs and add human context.
    LLM gets one clean number with a label — no scanning needed.
    """
    today = today_ist()
    day_of_year = today.timetuple().tm_yday

    _map = {
        "today": ("today_revenue_rupees",  "today_vs_yesterday_pct",
                  f"Today ({today.strftime('%d %b %Y')})", "vs yesterday", 1),
        "week":  ("week_revenue_rupees",   "week_vs_last_week_pct",
                  "This Week", "vs last week", 7),
        "month": ("month_revenue_rupees",  "month_vs_last_month_pct",
                  f"This Month ({today.strftime('%B %Y')})", "vs last month", today.day),
        "year":  ("year_revenue_rupees",   None,
                  f"This Year ({today.year})", None, day_of_year),
    }
    rev_field, pct_field, label, cmp_label, divisor = _map.get(period, _map["today"])
    revenue = rupees(kpis.get(rev_field) or 0)
    daily_avg = revenue / divisor if divisor else revenue

    result = {
        "period":               period,
        "period_label":         label,
        "revenue_rupees":       revenue,
        "daily_average_rupees": round(daily_avg),
        "verdict":              _revenue_verdict(daily_avg),
    }
    if pct_field:
        result["vs_previous_pct"]   = kpis.get(pct_field, 0)
        result["vs_previous_label"] = cmp_label
    return result


def extract_date_revenue(history_response, target_date: str) -> dict:
    """Find a specific date's revenue from a history array."""
    entries = _unwrap_history(history_response)
    for entry in entries:
        d = _entry_date(entry)
        if d == target_date:
            rev = _entry_revenue(entry)
            try:
                label = _date_label(_date.fromisoformat(d))
            except ValueError:
                label = d
            return {"date_label": label, "date": d, "revenue_rupees": rev}

    return {
        "date_label": target_date,
        "date": target_date,
        "revenue_rupees": None,
        "note": f"No revenue record found for {target_date}",
    }


def find_peak_day(
    history_response,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    """
    Find highest-revenue day in history, optionally within a date range.
    Returns a clear peak_day label so LLM doesn't have to scan the array.
    """
    raw = _unwrap_history(history_response)
    entries = []
    for entry in raw:
        d = _entry_date(entry)
        if not d:
            continue
        if from_date and d < from_date:
            continue
        if to_date and d > to_date:
            continue
        rev = _entry_revenue(entry)
        try:
            day_obj = _date.fromisoformat(d)
            entries.append({
                "date":           d,
                "day_name":       day_obj.strftime("%A"),
                "date_label":     day_obj.strftime("%d %b %Y"),
                "revenue_rupees": rev,
            })
        except ValueError:
            continue

    if not entries:
        return {"peak_day": None, "error": "No history data available for this range"}

    entries.sort(key=lambda x: x["date"])
    peak = max(entries, key=lambda x: x["revenue_rupees"])
    return {
        "peak_day":             f"{peak['day_name']}, {peak['date_label']}",
        "peak_revenue_rupees":  peak["revenue_rupees"],
        "all_days":             entries,
        "days_analyzed":        len(entries),
    }


def slim_menu(dishes: list) -> list:
    """Reduce raw dish objects to just what an answer needs: name, type, category,
    prices. The raw objects carry variants-as-JSON, ids, and flags that bloat the
    data block and make small models truncate or choke on menu listings.
    """
    import json as _json
    out = []
    for d in dishes:
        variants = d.get("variants") or []
        if isinstance(variants, str):
            try:
                variants = _json.loads(variants) if variants else []
            except ValueError:
                variants = []
        prices = [v.get("price") for v in variants
                  if isinstance(v, dict) and v.get("price") is not None]
        out.append({
            "name":     d.get("name"),
            "type":     d.get("type") or d.get("dish_type"),
            "category": d.get("category"),
            "prices":   prices,
        })
    return out


def summarize_trend(history_response, from_date: Optional[str] = None,
                    to_date: Optional[str] = None) -> dict:
    """Pre-compute trend stats so the LLM never has to do arithmetic over an array.

    Returns total, daily average, best/worst day, direction, and volatility for the
    days in range. A small model handed a 30-day array will miscompute these; here
    they're exact and the model just narrates the verdict.
    """
    raw = _unwrap_history(history_response)
    entries = []
    for entry in raw:
        d = _entry_date(entry)
        if not d:
            continue
        if from_date and d < from_date:
            continue
        if to_date and d > to_date:
            continue
        try:
            day_obj = _date.fromisoformat(d)
        except ValueError:
            continue
        entries.append({
            "date":           d,
            "day_name":       day_obj.strftime("%A"),
            "date_label":     day_obj.strftime("%d %b %Y"),
            "revenue_rupees": rupees(_entry_revenue(entry)),
        })

    if not entries:
        return {"note": "No revenue history available for this range"}

    entries.sort(key=lambda x: x["date"])
    revs = [e["revenue_rupees"] for e in entries]
    best = max(entries, key=lambda e: e["revenue_rupees"])
    worst = min(entries, key=lambda e: e["revenue_rupees"])
    direction = "up" if revs[-1] > revs[0] else "down" if revs[-1] < revs[0] else "flat"

    return {
        "days_analyzed":       len(entries),
        "total_rupees":        sum_rupees(revs),
        "avg_daily_rupees":    round(statistics.mean(revs)),
        "median_daily_rupees": round(statistics.median(revs)),
        "best_day":            f"{best['day_name']}, {best['date_label']} (₹{best['revenue_rupees']:,})",
        "worst_day":           f"{worst['day_name']}, {worst['date_label']} (₹{worst['revenue_rupees']:,})",
        "trend":               direction,
        "volatility_stdev_rupees": round(statistics.pstdev(revs)) if len(revs) > 1 else 0,
        "days":                entries,
    }


def flag_expenses(expenses_data: dict) -> dict:
    """Add high-expense warning and a type breakdown. LLM gets a verdict, not raw math."""
    total = rupees(expenses_data.get("total_rupees", 0))
    by_type: dict = {}
    for e in expenses_data.get("expenses", []):
        t = e.get("type") or e.get("name") or "other"
        by_type[t] = rupees(by_type.get(t, 0) + e.get("amount_rupees", 0))

    result = {**expenses_data, "breakdown_by_type": by_type, "is_high": total > 2000}
    if total > 2000:
        result["high_warning"] = f"₹{total:,.0f} exceeds the normal ₹2,000/day threshold"
    return result



def add_date_label(data: dict, date_str: str) -> dict:
    """Attach a human-readable date_label to any data dict."""
    try:
        label = _date_label(_date.fromisoformat(date_str))
    except (ValueError, TypeError):
        label = date_str or "unknown date"
    return {**data, "date_label": label}

"""Deterministic date resolution for LLM tools.

LLMs hallucinate date arithmetic — they'll happily turn 'kal' into the wrong
day. So we never trust the model to convert relative terms. Instead the tools
accept whatever the user said ('kal', 'yesterday', 'aaj', a YYYY-MM-DD string)
and this module resolves it in code, against IST — the dhaba's timezone.

Why IST matters: Render runs in UTC. `date.today()` there returns the UTC
date, which during the IST evening/night is still YESTERDAY. Resolving against
Asia/Kolkata keeps 'today'/'yesterday' correct for the dhaba owner.
"""

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")

# Relative term -> days to subtract from today (negative = future).
# Note: Hindi "kal" means both yesterday and tomorrow. For a business-data
# assistant the user is always asking about the PAST, so kal = yesterday.
_SINGLE = {
    "today": 0, "aaj": 0, "abhi": 0, "आज": 0, "aj": 0,
    "yesterday": 1, "kal": 1, "kal ka": 1, "कल": 1,
    "day before yesterday": 2, "parso": 2, "परसों": 2,
    "tomorrow": -1, "aane wala kal": -1,
}


def today_ist() -> date:
    """Current date in IST — NOT server-local (Render runs UTC)."""
    return datetime.now(_IST).date()


def is_iso_date(value) -> bool:
    """True if value is already a 'YYYY-MM-DD' string."""
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def resolve_day(value, default_today: bool = False):
    """Normalize whatever the LLM passes into a concrete YYYY-MM-DD string.

    Accepts: 'kal', 'yesterday', 'aaj', '2 days ago', a YYYY-MM-DD string, or None.
    - None -> today's date if default_today else None (None usually means
      "all dates" to the underlying API, so we preserve it).
    - An already-concrete YYYY-MM-DD passes through untouched.
    - An unparseable string falls back to today rather than passing garbage on.
    """
    if value is None:
        return today_ist().isoformat() if default_today else None

    if is_iso_date(value):
        return value

    v = str(value).lower().strip()

    if v in _SINGLE:
        return (today_ist() - timedelta(days=_SINGLE[v])).isoformat()

    m = re.match(r"(\d+)\s*(?:days?\s*ago|din\s*pehle)", v)
    if m:
        return (today_ist() - timedelta(days=int(m.group(1)))).isoformat()

    return today_ist().isoformat()


def resolve_range(value):
    """Resolve a relative RANGE term to (from_date, to_date) or None.

    Handles 'this week', 'last month', etc. Returns None if not a known range
    (the caller should then try resolve_day for a single day)."""
    v = str(value).lower().strip()
    t = today_ist()

    if v in ("this week", "is hafte", "is week"):
        start = t - timedelta(days=t.weekday())
        return start.isoformat(), t.isoformat()

    if v in ("last week", "pichle hafte"):
        start = t - timedelta(days=t.weekday() + 7)
        return start.isoformat(), (start + timedelta(days=6)).isoformat()

    if v in ("this month", "is mahine", "is month"):
        return t.replace(day=1).isoformat(), t.isoformat()

    if v in ("last month", "pichle mahine"):
        end = t.replace(day=1) - timedelta(days=1)
        return end.replace(day=1).isoformat(), end.isoformat()

    return None

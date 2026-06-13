"""Deterministic intent pre-filter — runs BEFORE the LLM classifier.

Unambiguous queries shouldn't cost an LLM call or risk misclassification:
- a 10-digit phone number  -> customer_balance (phone extracted)
- a bare greeting / thanks  -> general
- a clear menu/price phrase -> menu

Anything that doesn't match a rule returns None and falls through to the LLM
classifier in intent.py. rapidfuzz gives tolerance to typos/spacing without a
brittle exact-match list. Rules are intentionally conservative: when unsure,
return None and let the model decide.
"""

import re
from rapidfuzz import fuzz

# 10-digit Indian mobile, tolerant of spaces/dashes and an optional +91 / 0 prefix.
_PHONE_RE = re.compile(r"(?:\+?91[\-\s]?|0)?([6-9]\d{9})\b")

_GREETINGS = {
    "hi", "hello", "hey", "namaste", "namaskar", "yo", "hii", "helo",
    "thanks", "thank you", "thx", "shukriya", "dhanyavaad", "ok", "okay",
    "good morning", "good evening", "gm", "ge",
}

_MENU_PHRASES = (
    "menu", "price list", "rate list", "rate kya hai", "kya milta hai",
    "what do you serve", "dish list", "dishes list", "items list",
)


def _extract_phone(text: str) -> str | None:
    # Join digits split by a space/dash ("98765 43210" -> "9876543210") without
    # destroying word boundaries elsewhere. The leading [6-9] constraint keeps
    # stray digit runs from looking like phones.
    joined = re.sub(r"(?<=\d)[\s\-](?=\d)", "", text)
    m = _PHONE_RE.search(joined)
    return m.group(1) if m else None


def _is_greeting(text: str) -> bool:
    t = text.strip().lower().rstrip("!.?")
    if t in _GREETINGS:
        return True
    # very short and fuzzily close to a greeting (e.g. "helloo", "namastey")
    if len(t) <= 12:
        return any(fuzz.ratio(t, g) >= 88 for g in _GREETINGS)
    return False


def _is_menu(text: str) -> bool:
    t = text.strip().lower()
    if any(p in t for p in _MENU_PHRASES):
        return True
    return any(fuzz.partial_ratio(p, t) >= 90 for p in _MENU_PHRASES)


def prefilter(query: str) -> dict | None:
    """Return a partial IntentResult if a rule fires, else None.

    confidence is 1.0 — these are deterministic, not guesses. The caller fills
    in the remaining IntentResult fields (all None for these simple cases).
    """
    q = (query or "").strip()
    if not q:
        return None

    phone = _extract_phone(q)
    if phone:
        return {"intent": "customer_balance", "phone": phone, "confidence": 1.0}

    if _is_greeting(q):
        return {"intent": "general", "confidence": 1.0}

    if _is_menu(q):
        return {"intent": "menu", "confidence": 1.0}

    return None

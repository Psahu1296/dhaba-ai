"""Anti-hallucination tripwire.

Extracts every ₹-figure the model wrote and checks each against the verified
data block. A rupee number in the answer that doesn't appear in the data is a
hallucination signal — the model invented or miscomputed it.

Currently LOG-ONLY: we measure how often this fires before enabling any
enforcement (regenerate / block). Floats and Indian-comma formatting are
normalised so ₹2,400 matches 2400 and 2400.0.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

_RUPEE_RE = re.compile(r"₹\s*([\d,]+(?:\.\d+)?)")
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Baseline figures the assistant is told to cite for framing ("normal ~₹2,000",
# "slow day below ₹1,500"). These come from the system prompt, not the data, so
# they are legitimately "grounded" — without this the guard false-positives every
# time the model compares a real number to the baseline. Keep in sync with the
# Business Baseline section of pipeline/synthesizer.py:_SYSTEM.
_BASELINE_FIGURES = {"1000", "1500", "2000", "4000", "5000"}


def _normalise(token: str) -> str:
    """Strip commas and trailing .0 so 2,400 / 2400 / 2400.0 all compare equal."""
    t = token.replace(",", "")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t


def _grounded_numbers(data) -> set[str]:
    blob = json.dumps(data, ensure_ascii=False, default=str)
    return {_normalise(m) for m in _NUM_RE.findall(blob)}


def ungrounded_numbers(answer: str, data) -> list[str]:
    """₹-figures in the answer that don't appear anywhere in the data block.

    Small whole numbers (counts like "3 dishes", "2:00 PM") are ignored — only
    explicit ₹ amounts are checked, which is where fabrication actually hurts.
    """
    grounded = _grounded_numbers(data) | _BASELINE_FIGURES
    out = []
    for raw in _RUPEE_RE.findall(answer):
        n = _normalise(raw)
        if n and n not in grounded:
            out.append(raw)
    return out


def check(answer: str, data, *, query: str = "") -> list[str]:
    """Log-only check. Returns the list of ungrounded figures (empty = clean)."""
    if not data:
        return []
    bad = ungrounded_numbers(answer, data)
    if bad:
        logger.warning("guard | ungrounded ₹-figures %s | query=%r", bad, query[:80])
    return bad

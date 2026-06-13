"""Currency math in Decimal, never float.

Why: float sums drift (₹2,399.9999...), which both displays wrong and makes
eval equality checks flaky. We parse money via str(...) into Decimal, sum in
Decimal, and round to whole rupees (the dhaba deals in whole ₹) before handing
a number to the LLM. The LLM never does arithmetic — these helpers do.
"""

from decimal import Decimal, ROUND_HALF_UP


def rupees(value) -> int:
    """Coerce any money-ish value to a whole-rupee int. None/garbage -> 0."""
    try:
        return int(Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (ArithmeticError, ValueError, TypeError):
        return 0


def sum_rupees(values) -> int:
    """Sum an iterable of money-ish values in Decimal, return whole rupees."""
    total = Decimal(0)
    for v in values:
        try:
            total += Decimal(str(v or 0))
        except (ArithmeticError, ValueError, TypeError):
            continue
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

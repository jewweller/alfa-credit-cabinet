"""Positive-money arithmetic matching the inspected JS loanMath.ts, in kopecks."""

import math
from decimal import ROUND_HALF_UP, Decimal


def kopecks(value: str | float | int | Decimal) -> int:
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError("money must be finite and nonnegative")
    return int((number * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def money(value: str | float | int | Decimal) -> str:
    cents = kopecks(value)
    return f"{cents // 100}.{cents % 100:02d}"


def annuity_kopecks(amount_kopecks: int, rate: float, months: int) -> int:
    if amount_kopecks < 0 or months < 1 or not math.isfinite(rate) or rate < 0:
        raise ValueError("invalid annuity arguments")
    monthly = rate / 100 / 12
    payment = (
        amount_kopecks / months
        if monthly == 0
        else amount_kopecks * monthly / (1 - math.pow(1 + monthly, -months))
    )
    # Python round() is ties-to-even; JS Math.round() for positive values is not.
    return math.floor(payment + 0.5)


def monthly_payment(amount: str | float, rate: str | float, months: int) -> str:
    cents = annuity_kopecks(kopecks(amount), float(rate), months)
    return f"{cents // 100}.{cents % 100:02d}"


def maximum_amount(budget: float, rate: float, months: int, maximum: float) -> str:
    """Largest cent-denominated principal whose rounded payment fits the budget."""
    if budget <= 0:
        return "0.00"
    budget_cents = math.floor(budget * 100 + 1e-7)
    lo, hi = 0, kopecks(maximum)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if annuity_kopecks(mid, rate, months) <= budget_cents:
            lo = mid
        else:
            hi = mid - 1
    return f"{lo // 100}.{lo % 100:02d}"

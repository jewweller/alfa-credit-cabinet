"""Кредитная математика (план, раздел 7: «Платёж — аннуитет»).

Расчёты точные, без округления. Правило округления передаёт вызывающий код из
scoring/config.yaml (`round_money`); здесь оно не зашито. График платежей — TBD.
"""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext
from typing import Literal

_ROUNDING = {"half_up": ROUND_HALF_UP, "down": ROUND_DOWN}

# Запас точности, чтобы результат не зависел от глобального контекста Decimal.
_PRECISION = 34


def annuity_payment(amount: Decimal, annual_rate_pct: Decimal, term_months: int) -> Decimal:
    """Ежемесячный аннуитетный платёж без округления.

    Месячная ставка r = annual_rate_pct / 12 / 100; платёж = amount · r / (1 − (1 + r)^−n).
    При ставке 0% платёж равен amount / term_months.
    """
    if not isinstance(amount, Decimal) or not isinstance(annual_rate_pct, Decimal):
        raise TypeError("amount и annual_rate_pct должны быть Decimal")
    if isinstance(term_months, bool) or not isinstance(term_months, int):
        raise TypeError("term_months должен быть int")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("сумма должна быть больше нуля")
    if not annual_rate_pct.is_finite() or annual_rate_pct < 0:
        raise ValueError("ставка не может быть отрицательной")
    if term_months < 1:
        raise ValueError("срок должен быть не меньше 1 месяца")

    with localcontext() as ctx:
        ctx.prec = _PRECISION
        if annual_rate_pct == 0:
            return amount / term_months
        monthly_rate = annual_rate_pct / 12 / 100
        return amount * monthly_rate / (1 - (1 + monthly_rate) ** -term_months)


def max_principal(payment: Decimal, annual_rate_pct: Decimal, term_months: int) -> Decimal:
    """Обратный аннуитет: наибольшая сумма, платёж по которой равен payment. Без округления."""
    if payment <= 0:
        return Decimal(0)
    with localcontext() as ctx:
        ctx.prec = _PRECISION
        if annual_rate_pct == 0:
            return payment * term_months
        monthly_rate = annual_rate_pct / 12 / 100
        return payment * (1 - (1 + monthly_rate) ** -term_months) / monthly_rate


def round_money(value: Decimal, mode: Literal["half_up", "down"], step: Decimal) -> Decimal:
    """Округление до шага step (1 — рубль, 0.01 — копейка, 1000 — тысяча) по правилу mode."""
    if step <= 0:
        raise ValueError("шаг округления должен быть больше нуля")
    units = (value / step).quantize(Decimal(1), rounding=_ROUNDING[mode])
    return (units * step).quantize(Decimal("0.01"))

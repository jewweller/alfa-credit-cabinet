"""Кредитная математика (план, раздел 7: «Платёж — аннуитет»).

Расчёты точные, без округления. Правило округления передаёт вызывающий код из
scoring/config.yaml (`round_money`); здесь оно не зашито. График — `annuity_schedule`.
"""

from dataclasses import dataclass
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


@dataclass(frozen=True)
class ScheduleRow:
    number: int
    payment: Decimal
    principal: Decimal
    interest: Decimal
    balance: Decimal


def annuity_schedule(
    amount: Decimal,
    annual_rate_pct: Decimal,
    term_months: int,
    payment: Decimal,
    interest_step: Decimal,
    interest_mode: Literal["half_up", "down"],
) -> list[ScheduleRow]:
    """Помесячный график при заданном (уже округлённом) платеже.

    Проценты за месяц = остаток × годовая ставка / 12 / 100, округляются по interest_step и
    interest_mode; основной долг = платёж − проценты; последний платёж закрывает остаток.
    """
    if amount <= 0 or term_months < 1 or payment <= 0:
        raise ValueError("сумма, срок и платёж должны быть больше нуля")
    with localcontext() as ctx:
        ctx.prec = _PRECISION
        monthly_rate = annual_rate_pct / 12 / 100
        balance = amount
        rows: list[ScheduleRow] = []
        for number in range(1, term_months + 1):
            interest = round_money(balance * monthly_rate, interest_mode, interest_step)
            last = number == term_months
            principal = balance if last else payment - interest
            if principal <= 0 and not last:
                raise ValueError("платёж не покрывает проценты: график не сходится")
            principal = min(principal, balance)
            balance -= principal
            rows.append(ScheduleRow(number, principal + interest, principal, interest, balance))
        return rows

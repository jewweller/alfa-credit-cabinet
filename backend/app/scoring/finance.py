"""Платёж и долговая нагрузка по правилам из config.yaml — общие для скоринга и решения."""

from decimal import Decimal

from app.domain.loan_math import annuity_payment, round_money
from app.scoring.config import EngineConfig
from app.scoring.inputs import ApplicantSources, LoanRequest, SourceState


def monthly_payment(
    config: EngineConfig, amount: Decimal, annual_rate_pct: Decimal, term_months: int
) -> Decimal:
    rule = config.calculation.rounding["payment"]
    return round_money(
        annuity_payment(amount, annual_rate_pct, term_months), rule.mode, rule.step_rub
    )


def existing_payments(
    config: EngineConfig, request: LoanRequest, sources: ApplicantSources
) -> Decimal:
    """E = анкета или max(анкета, сумма платежей БКИ), если БКИ ответило (config.debt_load)."""
    payments = request.existing_payments_monthly
    if config.calculation.debt_load.include_bki_payments and sources.bki.state == SourceState.OK:
        assert sources.bki.data is not None
        bki_total = sum((loan.monthly_payment for loan in sources.bki.data.loans), Decimal(0))
        payments = max(payments, bki_total)
    return payments


def latest_fns_revenue(sources: ApplicantSources) -> Decimal | None:
    if sources.fns.state != SourceState.OK or sources.fns.data is None:
        return None
    revenue = sources.fns.data.revenue_by_year
    return revenue[max(revenue)] if revenue else None


def monthly_revenue(
    config: EngineConfig, request: LoanRequest, sources: ApplicantSources
) -> Decimal:
    revenue = request.revenue_12m
    if config.calculation.debt_load.revenue_source == "min_application_fns":
        fns = latest_fns_revenue(sources)
        if fns is not None:
            revenue = min(revenue, fns)
    return revenue / 12


def debt_load_pct(
    config: EngineConfig,
    request: LoanRequest,
    sources: ApplicantSources,
    new_payment: Decimal,
) -> Decimal | None:
    """(E + платёж) / (выручка / 12) × 100. None — выручка ≤ 0, нагрузку посчитать нельзя."""
    revenue = monthly_revenue(config, request, sources)
    if revenue <= 0:
        return None
    return (existing_payments(config, request, sources) + new_payment) / revenue * 100

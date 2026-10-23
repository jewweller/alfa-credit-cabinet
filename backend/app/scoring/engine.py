"""Скоринг F1–F6 → балл 0–100 и грейд A–E (план, раздел 7). Все пороги — из config.yaml.

Скоринг отвечает только на вопрос «насколько рискованный клиент». Что предложить — решает
decision/engine.py. Скоринг считается всегда, даже если решение — отказ по стоп-фактору.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from app.scoring.config import EngineConfig, Factor, Grade, load_config
from app.scoring.finance import debt_load_pct, monthly_payment
from app.scoring.inputs import ApplicantSources, LoanRequest, SourceState


@dataclass(frozen=True)
class FactorResult:
    id: str
    name: str
    value: Decimal | None  # исходное значение в единицах фактора; None — нет данных
    band: str | None  # id диапазона из конфига; None — сработало no_data / no_history / missing
    points: int
    max_points: int
    note: str | None = None


@dataclass(frozen=True)
class ScoringResult:
    config_version: str
    reference_date: date
    total: int
    grade: Grade
    factors: tuple[FactorResult, ...]
    new_payment_base_rate: Decimal  # платёж по новому кредиту по базовой ставке (для F3)
    debt_load_pct: Decimal | None

    def factor(self, factor_id: str) -> FactorResult:
        return next(f for f in self.factors if f.id == factor_id)


def full_years(start: date, on: date) -> int:
    """Полные годовщины: 2024-04-10 → 2026-04-09 = 1 год, 2026-04-10 = 2 года."""
    return on.year - start.year - ((on.month, on.day) < (start.month, start.day))


def _banded(
    factor_id: str, factor: Factor, value: Decimal, note: str | None = None
) -> FactorResult:
    band = factor.band_for(value)
    return FactorResult(
        factor_id, factor.name, value, band.id, band.points, factor.max_points, note
    )


def _special(
    factor_id: str, factor: Factor, points: int, note: str, value: Decimal | None = None
) -> FactorResult:
    return FactorResult(factor_id, factor.name, value, None, points, factor.max_points, note)


def score(
    request: LoanRequest,
    sources: ApplicantSources,
    config: EngineConfig | None = None,
    reference_date: date | None = None,
) -> ScoringResult:
    config = config or load_config()
    factors = config.scoring.factors
    missing = config.scoring.missing_source_points
    on = reference_date or config.scoring.reference_date or datetime.now(UTC).date()
    results: list[FactorResult] = []

    # F1 — возраст бизнеса по реестру.
    f1 = factors["F1"]
    if sources.registry.state == SourceState.OK and sources.registry.data is not None:
        years = Decimal(full_years(sources.registry.data.registered_at, on))
        results.append(_banded("F1", f1, years))
    else:
        results.append(_special("F1", f1, missing, f"реестр: {sources.registry.state}"))

    # F2 — кредитная история: худшая просрочка за 24 месяца по всем кредитам.
    f2 = factors["F2"]
    bki = sources.bki.data
    if sources.bki.state != SourceState.OK or bki is None:
        results.append(_special("F2", f2, missing, f"БКИ: {sources.bki.state}"))
    elif not bki.has_history:
        assert f2.no_history_points is not None
        results.append(_special("F2", f2, f2.no_history_points, "нет кредитной истории"))
    else:
        worst = max((loan.max_overdue_days_24m for loan in bki.loans), default=0)
        results.append(_banded("F2", f2, Decimal(worst)))

    # F3 — нагрузка с новым платежом по базовой ставке продукта.
    f3 = factors["F3"]
    payment = monthly_payment(
        config, request.amount, request.product.base_rate, request.term_months
    )
    load = debt_load_pct(config, request, sources, payment)
    if load is None:
        results.append(_special("F3", f3, missing, "выручка ≤ 0: нагрузку посчитать нельзя"))
    else:
        results.append(_banded("F3", f3, load))

    # F4–F6 — ФНС «Прозрачный бизнес».
    f4, f5, f6 = factors["F4"], factors["F5"], factors["F6"]
    fns = sources.fns.data
    if sources.fns.state != SourceState.OK or fns is None:
        note = f"ФНС: {sources.fns.state}"
        results += [
            _special(fid, f, missing, note) for fid, f in (("F4", f4), ("F5", f5), ("F6", f6))
        ]
    else:
        revenue = fns.revenue_by_year
        last = max(revenue) if revenue else None
        previous = revenue.get(last - 1) if last is not None else None
        assert f4.no_data_points is not None
        if last is None or previous is None or previous <= 0:
            results.append(_special("F4", f4, f4.no_data_points, "нет данных за предыдущий год"))
        else:
            growth = (revenue[last] - previous) / previous * 100
            results.append(_banded("F4", f4, growth, f"{last} к {last - 1}"))
        results.append(_banded("F5", f5, fns.tax_debt_rub))
        assert f6.flags is not None
        raised = [flag for flag in f6.flags if fns.flags.get(flag)]
        results.append(_banded("F6", f6, Decimal(len(raised)), ", ".join(raised) or None))

    total = sum(r.points for r in results)
    grade = next(g.grade for g in config.scoring.grades if total >= g.min_score)
    return ScoringResult(
        config_version=config.config_version,
        reference_date=on,
        total=total,
        grade=grade,
        factors=tuple(results),
        new_payment_base_rate=payment,
        debt_load_pct=load,
    )

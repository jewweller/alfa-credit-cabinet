"""Ответы источников по контрактам моков (план, раздел 8) → входные данные движков."""

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from app.integrations.base import FetchResult
from app.scoring.inputs import (
    ApplicantSources,
    BkiLoan,
    BkiReport,
    FnsProfile,
    RegistryData,
    Source,
    SourceState,
)


def _money(value: Any) -> Decimal:
    return Decimal(str(value))


def _source[T](result: FetchResult, parse: Any) -> Source[T]:
    if result.state != SourceState.OK:
        return Source(result.state)
    assert result.payload is not None
    return Source.ok(parse(result.payload))


def _registry(payload: dict[str, Any]) -> RegistryData:
    return RegistryData(
        status=payload["status"], registered_at=date.fromisoformat(payload["registered_at"])
    )


def _fns(payload: dict[str, Any]) -> FnsProfile:
    return FnsProfile(
        revenue_by_year={int(year): _money(v) for year, v in payload["revenue"].items()},
        tax_debt_rub=_money(payload["tax_debt_rub"]),
        flags={name: bool(v) for name, v in payload.get("flags", {}).items()},
    )


def _bki(payload: dict[str, Any]) -> BkiReport:
    return BkiReport(
        has_history=bool(payload["has_history"]),
        bankruptcy=bool(payload["bankruptcy"]),
        loans=tuple(
            BkiLoan(
                monthly_payment=_money(loan["monthly_payment"]),
                max_overdue_days_24m=int(loan["max_overdue_days_24m"]),
                current_overdue_days=int(loan["current_overdue_days"]),
            )
            for loan in payload.get("loans", [])
        ),
    )


def to_applicant_sources(
    kind: Literal["LLC", "IE"], results: dict[str, FetchResult]
) -> ApplicantSources:
    """Бросает KeyError / ValueError на ответе не по контракту — это сбой, а не бизнес-итог."""
    registry = results["egrul" if kind == "LLC" else "egrip"]
    return ApplicantSources(
        company_kind=kind,
        registry=_source(registry, _registry),
        fns=_source(results["fns_tb"], _fns),
        bki=_source(results["bki"], _bki),
    )

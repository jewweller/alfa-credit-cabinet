"""Входные данные движков: анкета, продукт и ответы источников в нормализованном виде.

Разбор JSON ЕГРЮЛ / ЕГРИП / ФНС / БКИ в эти структуры — задача адаптеров интеграций
(конвейер). Движки работают только с этими структурами и не ходят в сеть.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID


class SourceState(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"  # 404 реестра: компании нет (это ответ, а не сбой)
    UNAVAILABLE = "unavailable"  # не ответил после всех повторов


@dataclass(frozen=True)
class RegistryData:
    status: str
    registered_at: date


@dataclass(frozen=True)
class BkiLoan:
    monthly_payment: Decimal
    max_overdue_days_24m: int
    current_overdue_days: int


@dataclass(frozen=True)
class BkiReport:
    has_history: bool
    bankruptcy: bool
    loans: tuple[BkiLoan, ...] = ()


@dataclass(frozen=True)
class FnsProfile:
    revenue_by_year: dict[int, Decimal]
    tax_debt_rub: Decimal
    flags: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class Source[T]:
    state: SourceState
    data: T | None = None

    @classmethod
    def ok(cls, data: T) -> "Source[T]":
        return cls(SourceState.OK, data)

    @classmethod
    def not_found(cls) -> "Source[T]":
        return cls(SourceState.NOT_FOUND)

    @classmethod
    def unavailable(cls) -> "Source[T]":
        return cls(SourceState.UNAVAILABLE)


@dataclass(frozen=True)
class ProductTerms:
    """Продукт из таблицы products (источник — seed/products.json)."""

    id: UUID | str
    code: str
    name: str
    purposes: tuple[str, ...]
    min_amount: Decimal
    max_amount: Decimal
    min_term: int
    max_term: int
    base_rate: Decimal


@dataclass(frozen=True)
class LoanRequest:
    """Анкета заявки на момент отправки (все поля уже проверены submit)."""

    product: ProductTerms
    amount: Decimal
    term_months: int
    purpose: str
    revenue_12m: Decimal
    existing_payments_monthly: Decimal


@dataclass(frozen=True)
class ApplicantSources:
    company_kind: Literal["LLC", "IE"]
    registry: Source[RegistryData]
    fns: Source[FnsProfile]
    bki: Source[BkiReport]

    @property
    def registry_source(self) -> str:
        return "egrul" if self.company_kind == "LLC" else "egrip"

    def state_of(self, source: str) -> SourceState:
        by_name = {self.registry_source: self.registry, "fns_tb": self.fns, "bki": self.bki}
        return by_name[source].state

"""Кабинет банка: очередь, карточка андеррайтера и решение (план, разделы 7, 8, 10, 11 — B2–B4).

В отличие от клиентских схем здесь видно всё: ответы источников как есть, скоринг по
факторам F1–F6, проверку правил R1–R10 и кто принял решение.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.state_machine import ApplicationStatus
from app.schemas.applications import ApplicationDetail
from app.schemas.common import Money, Rate
from app.schemas.companies import CompanyBrief, CompanyLookupResponse
from app.schemas.decisions import DecisionActor, DecisionOutcome, RejectReason
from app.schemas.documents import InfoRequestItem


class Grade(StrEnum):
    """Грейд по баллу скоринга: A ≥ 80, B 65–79, C 50–64, D 35–49, E < 35."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class Employee(BaseModel):
    """Сотрудник банка — кто взял заявку в работу или принял решение."""

    id: UUID
    full_name: str = Field(examples=["Дмитрий Орлов"])


class BankApplicationSummary(BaseModel):
    """Строка очереди (экран B2)."""

    id: UUID
    number: str = Field(examples=["1051"])
    company: CompanyBrief
    product_id: UUID | None
    amount: Money | None
    term_months: int | None
    status: ApplicationStatus
    status_changed_at: datetime = Field(description="С этого момента считается «время в статусе».")
    submitted_at: datetime | None
    score: int | None = Field(ge=0, le=100, description="Балл скоринга; null, пока не посчитан.")
    grade: Grade | None = Field(description="Грейд; null, пока скоринг не посчитан.")
    assignee: Employee | None = Field(description="Кто взял в работу; null — никто.")


class EnrichmentSource(StrEnum):
    EGRUL = "egrul"
    EGRIP = "egrip"
    FNS_TB = "fns_tb"
    BKI = "bki"


class EnrichmentStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    ERROR = "error"


class EnrichmentResult(BaseModel):
    """Ответ внешнего источника на этапе обогащения (таблица `enrichment_results`)."""

    source: EnrichmentSource
    status: EnrichmentStatus
    attempts: int = Field(ge=1, description="Сколько было попыток: при сбое — до 3 (2 повтора).")
    fetched_at: datetime
    response: dict[str, Any] | None = Field(
        description="Ответ источника как есть (сырой JSON мока); null при ошибке."
    )


class ScoringFactor(BaseModel):
    code: str = Field(pattern=r"^F[1-6]$", examples=["F3"])
    title: str = Field(examples=["Долговая нагрузка"])
    value: str = Field(description="Значение фактора понятными словами.", examples=["21,3%"])
    points: int = Field(ge=0)
    max_points: int = Field(ge=1)


class ScoringResult(BaseModel):
    """Скоринг — отдельно от решения (план, раздел 7). Считается всегда, даже при отказе."""

    model_version: str = Field(examples=["rules-2026.10"])
    total_score: int = Field(ge=0, le=100)
    grade: Grade
    debt_load: float = Field(
        ge=0,
        description=(
            "Нагрузка долей: (текущие платежи + платёж по новому кредиту) / месячная выручка. "
            "Платёж — по базовой ставке продукта на запрошенных условиях."
        ),
        examples=[0.213],
    )
    factors: list[ScoringFactor] = Field(description="F1–F6 по порядку.")


class RuleCheck(BaseModel):
    """Проверка одного правила движка решения. Правила идут по порядку, срабатывает первое."""

    code: str = Field(pattern=r"^R([1-9]|10)$", examples=["R4"])
    title: str = Field(examples=["Выручка в анкете расходится с ФНС больше чем на 30%"])
    fired: bool = Field(description="true — правило сработало и определило исход.")
    detail: str | None = Field(description="Почему сработало или почему нет, с цифрами.")


class BankDecision(BaseModel):
    """Последнее решение по заявке глазами банка: в отличие от клиентского — с комментарием."""

    outcome: DecisionOutcome
    decided_by: DecisionActor
    reason_code: RejectReason | None = Field(description="Только для `outcome = rejected`.")
    decided_at: datetime
    underwriter: Employee | None = Field(description="Кто решил; null — решил движок.")
    comment: str | None = Field(description="Внутренний комментарий специалиста.")


class BankApplicationDetail(BaseModel):
    """Полная карточка для андеррайтера (экран B3)."""

    application: ApplicationDetail
    company: CompanyBrief
    applicant_name: str = Field(description="Кто из клиента подал заявку.")
    registry: CompanyLookupResponse | None = Field(
        description="Данные ЕГРЮЛ / ЕГРИП в едином виде; null — компании нет в реестре."
    )
    assignee: Employee | None
    enrichment: list[EnrichmentResult] = Field(
        description="Ответы источников; пустой список, пока обогащение не прошло."
    )
    scoring: ScoringResult | None = Field(description="null, пока скоринг не посчитан.")
    rules: list[RuleCheck] = Field(
        description="Проверка R1–R10 по порядку до сработавшего; пусто, пока решения не было."
    )
    decision: BankDecision | None


class UnderwriterOutcome(StrEnum):
    """Исход ручного рассмотрения: те же 4, что у движка, кроме «на ручное рассмотрение»."""

    APPROVED = "approved"
    COUNTER_OFFER = "counter_offer"
    INFO_REQUESTED = "info_requested"
    REJECTED = "rejected"


class UnderwriterDecisionRequest(BaseModel):
    """Решение специалиста (экран B4). Какие поля нужны — зависит от `outcome`."""

    model_config = ConfigDict(extra="forbid")

    outcome: UnderwriterOutcome
    product_id: UUID | None = Field(
        default=None, description="`counter_offer`: продукт оффера. Иначе не передаётся."
    )
    amount: Money | None = Field(default=None, description="`counter_offer`: сумма оффера.")
    term_months: int | None = Field(default=None, ge=1, description="`counter_offer`: срок оффера.")
    rate: Rate | None = Field(
        default=None,
        description=(
            "`approved` и `counter_offer`: ставка. Для `approved` сумма и срок — из заявки."
        ),
    )
    info_items: list[InfoRequestItem] | None = Field(
        default=None, description="`info_requested`: какие документы нужны (хотя бы один)."
    )
    reason_code: RejectReason | None = Field(
        default=None, description="`rejected`: причина из справочника."
    )
    comment: str | None = Field(
        default=None,
        max_length=1000,
        description=(
            "`info_requested`: сообщение клиенту (обязательно). "
            "Для остальных исходов — внутренний комментарий, клиент его не видит."
        ),
    )

    @model_validator(mode="after")
    def _fields_match_outcome(self) -> Self:
        needed: dict[UnderwriterOutcome, tuple[str, ...]] = {
            UnderwriterOutcome.APPROVED: ("rate",),
            UnderwriterOutcome.COUNTER_OFFER: ("product_id", "amount", "term_months", "rate"),
            UnderwriterOutcome.INFO_REQUESTED: ("info_items", "comment"),
            UnderwriterOutcome.REJECTED: ("reason_code",),
        }
        for field in needed[self.outcome]:
            if not getattr(self, field):
                raise ValueError(f"для outcome={self.outcome} нужно поле {field}")
        return self

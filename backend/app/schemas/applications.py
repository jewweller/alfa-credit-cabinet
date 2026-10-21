"""Схемы заявки и оффера (план, разделы 4, 6, 9, 10)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.state_machine import ApplicationStatus
from app.schemas.common import Money, Rate
from app.schemas.products import LoanPurpose

_NUMBER_DESCRIPTION = "Номер заявки. В плане тип string, формат не определён (TBD)."


class ApplicationCreate(BaseModel):
    """Создание черновика (`DRAFT`).

    TBD: как определяется компания заявки — из профиля пользователя или по ИНН,
    введённому в мастере, — не согласовано. Поле для ИНН может быть добавлено.
    """

    model_config = ConfigDict(extra="forbid")

    product_id: UUID | None = None
    amount: Money | None = None
    term_months: int | None = Field(default=None, ge=1)
    purpose: LoanPurpose | None = None


class ApplicationUpdate(BaseModel):
    """Автосохранение черновика. Передаются только изменяемые поля.

    `version` обязателен: если заявку уже изменили, ответ 409 `version_conflict` (план, раздел 9).
    В каких статусах разрешено изменение — TBD.
    """

    model_config = ConfigDict(extra="forbid")

    version: int = Field(description="Версия заявки, полученная последним GET.")
    product_id: UUID | None = None
    amount: Money | None = None
    term_months: int | None = Field(default=None, ge=1)
    purpose: LoanPurpose | None = None
    revenue_12m: Money | None = Field(default=None, description="Выручка за 12 месяцев, рублей.")
    existing_payments_monthly: Money | None = Field(
        default=None, description="Текущие платежи по кредитам в месяц, рублей."
    )
    bki_consent: bool | None = Field(default=None, description="Согласие на запрос в БКИ.")


class OfferStatus(StrEnum):
    ACTIVE = "active"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class Offer(BaseModel):
    id: UUID
    product_id: UUID
    amount: Money
    term_months: int
    rate: Rate
    monthly_payment: Money
    status: OfferStatus


class ApplicationSummary(BaseModel):
    id: UUID
    number: str = Field(description=_NUMBER_DESCRIPTION)
    status: ApplicationStatus
    product_id: UUID | None
    amount: Money | None
    term_months: int | None
    submitted_at: datetime | None


class ApplicationDetail(BaseModel):
    """Заявка целиком. Тексты статусов и «что дальше» — на фронте (`i18n/ru.ts`, план, раздел 13).

    Поля черновика могут быть пустыми, пока заявка в `DRAFT`.
    """

    id: UUID
    number: str = Field(description=_NUMBER_DESCRIPTION)
    company_id: UUID
    applicant_id: UUID
    product_id: UUID | None
    amount: Money | None
    term_months: int | None
    purpose: LoanPurpose | None
    revenue_12m: Money | None
    existing_payments_monthly: Money | None
    bki_consent: bool
    status: ApplicationStatus
    version: int
    submitted_at: datetime | None
    active_offer: Offer | None = Field(description="Активный оффер, если он есть.")

"""Схемы каталога продуктов (план, разделы 6 и 7)."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money, Rate


class LoanPurpose(StrEnum):
    """Цель кредита: оборотные средства / оборудование / кассовый разрыв (план, раздел 4).

    Коды — предварительный контракт: в плане цели названы только по-русски, TBD.
    """

    WORKING_CAPITAL = "working_capital"
    EQUIPMENT = "equipment"
    CASH_GAP = "cash_gap"


class Product(BaseModel):
    id: UUID
    code: str = Field(examples=["EXPRESS_WC"])
    name: str = Field(examples=["Экспресс-оборот"])
    purpose_tags: list[LoanPurpose]
    min_amount: Money
    max_amount: Money
    min_term: int = Field(description="Минимальный срок, месяцев.")
    max_term: int = Field(description="Максимальный срок, месяцев.")
    base_rate: Rate


class ProductRecommendRequest(BaseModel):
    """Параметры подбора продукта (экран C3): на что нужны деньги, сколько и на какой срок."""

    model_config = ConfigDict(extra="forbid")

    purpose: LoanPurpose
    amount: Money = Field(description="Желаемая сумма, рублей.")
    term_months: int = Field(ge=1, description="Желаемый срок, месяцев.")


class RecommendationAdjustment(StrEnum):
    """Какой параметр подбора изменён, чтобы попасть в лимиты продукта."""

    AMOUNT = "amount"
    TERM_MONTHS = "term_months"


class ProductRecommendation(BaseModel):
    """Подходящий продукт с примерным платежом.

    Сумма и срок приведены к лимитам продукта; что изменено — в `adjusted`.
    Платёж — аннуитет по базовой ставке, итоговую ставку определит решение банка.
    """

    product: Product
    amount: Money = Field(description="Сумма для расчёта: запрошенная, приведённая к лимитам.")
    term_months: int = Field(description="Срок для расчёта: запрошенный, приведённый к лимитам.")
    rate: Rate = Field(description="Базовая ставка продукта.")
    monthly_payment: Money = Field(description="Примерный ежемесячный платёж.")
    adjusted: list[RecommendationAdjustment] = Field(
        description="Изменённые параметры; пусто — продукт подходит на запрошенных условиях."
    )

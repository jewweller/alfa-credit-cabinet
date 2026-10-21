"""Схемы каталога продуктов (план, разделы 6 и 7)."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

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

"""Кредитное решение глазами клиента (план, разделы 4, 7 и 11).

Клиенту не показываем скоринг, баллы и сработавшие правила — только итог, кто решил
и код причины отказа. Тексты «почему» и «что можно сделать» — на фронте по коду.
"""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import DescribedStrEnum


class DecisionOutcome(StrEnum):
    APPROVED = "approved"
    COUNTER_OFFER = "counter_offer"
    REJECTED = "rejected"
    INFO_REQUESTED = "info_requested"
    MANUAL_REVIEW = "manual_review"


class DecisionActor(StrEnum):
    SYSTEM = "system"
    UNDERWRITER = "underwriter"


class RejectReason(DescribedStrEnum):
    """Причина отказа. Коды привязаны к правилам движка решения (план, раздел 7)."""

    COMPANY_INACTIVE = "company_inactive"
    BANKRUPTCY_OR_OVERDUE = "bankruptcy_or_overdue"
    LOW_SCORE = "low_score"
    NO_SUITABLE_TERMS = "no_suitable_terms"
    UNDERWRITER_DECISION = "underwriter_decision"

    @classmethod
    def value_descriptions(cls) -> Mapping[str, str]:
        return REJECT_REASON_DESCRIPTIONS


REJECT_REASON_DESCRIPTIONS: Mapping[str, str] = {
    RejectReason.COMPANY_INACTIVE: (
        "R1, компания ликвидирована: статус в ЕГРЮЛ/ЕГРИП не «действующая»"
    ),
    RejectReason.BANKRUPTCY_OR_OVERDUE: (
        "R2, банкротство или текущая просрочка больше 90 дней по данным БКИ"
    ),
    RejectReason.LOW_SCORE: "R6, грейд E: скоринговый балл ниже 35",
    RejectReason.NO_SUITABLE_TERMS: (
        "R10, нагрузка выше 35%, и не подошли ни более длинный срок, "
        "ни меньшая сумма, ни другой продукт"
    ),
    RejectReason.UNDERWRITER_DECISION: "ручной отказ кредитного специалиста (этап 6)",
}


class ClientDecision(BaseModel):
    """Последнее решение по заявке в том виде, в каком его видит клиент."""

    outcome: DecisionOutcome
    decided_by: DecisionActor
    reason_code: RejectReason | None = Field(
        description="Только для `outcome = rejected`, иначе null."
    )
    decided_at: datetime

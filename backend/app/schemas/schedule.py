"""График платежей по офферу (план, разделы 3 и 11). Аннуитет, `domain/loan_math.py`."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import Money, Rate


class PaymentScheduleItem(BaseModel):
    number: int = Field(ge=1, description="Номер платежа, с 1.")
    due_date: date
    payment: Money = Field(description="Сумма платежа.")
    principal: Money = Field(description="Из неё в погашение долга.")
    interest: Money = Field(description="Из неё проценты.")
    balance: Money = Field(description="Остаток долга после платежа.")


class PaymentSchedule(BaseModel):
    """Аннуитетный график.

    Суммы округляются до копеек, последний платёж закрывает остаток целиком.
    Дата первого платежа — через месяц после выдачи, до выдачи — от текущей даты (TBD).
    """

    offer_id: UUID
    amount: Money
    term_months: int
    rate: Rate
    monthly_payment: Money
    total_payment: Money = Field(description="Сумма всех платежей.")
    overpayment: Money = Field(description="Переплата: всего платежей минус сумма кредита.")
    items: list[PaymentScheduleItem]

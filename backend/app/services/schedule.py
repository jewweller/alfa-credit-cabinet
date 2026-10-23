"""График платежей по офферу (план, разделы 3 и 11; схема PaymentSchedule в контракте).

Временные правила backend (B8, docs/analyst-questions.md) — аналитиком не подтверждены:
  * ежемесячный платёж — сохранённый в оффере (его округление — config.yaml, вопрос K1);
  * проценты за месяц — calculation.rounding.interest (сейчас до копейки, вопрос M4);
  * последний платёж закрывает остаток (описание графика в контракте, вопрос M3);
  * даты — от сегодняшнего дня: выдачи ещё нет, контракт говорит «до выдачи — от текущей
    даты» (вопрос M6); дальше то же число месяца, а если его нет — последний день месяца.
"""

import calendar
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.models import OfferRow, User
from app.domain.loan_math import annuity_schedule
from app.schemas.common import ErrorCode
from app.schemas.schedule import PaymentSchedule, PaymentScheduleItem
from app.scoring.config import EngineConfig, load_config
from app.services.applications import _latest, get_visible

_NO_OFFER = "Заявка не найдена или по ней нет оффера"


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def build(
    session: Session,
    user: User,
    application_id: UUID,
    offer_id: UUID | None,
    config: EngineConfig | None = None,
    today: date | None = None,
) -> PaymentSchedule:
    config = config or load_config()
    application = get_visible(session, user, application_id)
    if offer_id is not None:
        offer = session.get(OfferRow, offer_id)
        if offer is None or offer.application_id != application.id:
            raise ApiError(404, ErrorCode.NOT_FOUND, _NO_OFFER)
    else:
        # Последний оффер: пока он действует — активный, после ответа клиента — принятый.
        offer = _latest(session, OfferRow, application)
        if offer is None:
            raise ApiError(404, ErrorCode.NOT_FOUND, _NO_OFFER)

    rule = config.calculation.rounding["interest"]
    rows = annuity_schedule(
        offer.amount, offer.rate, offer.term_months, offer.monthly_payment, rule.step_rub, rule.mode
    )
    start = today or datetime.now(UTC).date()
    total = sum((row.payment for row in rows), Decimal(0))
    return PaymentSchedule(
        offer_id=offer.id,
        amount=offer.amount,
        term_months=offer.term_months,
        rate=offer.rate,
        monthly_payment=offer.monthly_payment,
        total_payment=total,
        overpayment=total - offer.amount,
        items=[
            PaymentScheduleItem(
                number=row.number,
                due_date=add_months(start, row.number),
                payment=row.payment,
                principal=row.principal,
                interest=row.interest,
                balance=row.balance,
            )
            for row in rows
        ],
    )

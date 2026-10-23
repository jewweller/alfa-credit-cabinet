"""Ответ клиента на оффер (план, раздел 4, этап 7; статусы — раздел 5).

Принять: APPROVED / COUNTER_OFFER → SIGNING, оффер `accepted`.
Отказаться: APPROVED / COUNTER_OFFER → DECLINED_BY_CLIENT, оффер `declined`.
Ответить можно только на действующий (`active`) оффер своей заявки; повтор — 409.
"""

from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.errors import ApiError
from app.db.models import Application, OfferRow, User
from app.domain.state_machine import ApplicationStatus
from app.schemas.applications import OfferStatus
from app.schemas.common import ErrorCode
from app.services.applications import get_visible
from app.services.status import change_status


def _offer_of(session: Session, application: Application, offer_id: UUID) -> OfferRow:
    offer = session.get(OfferRow, offer_id)
    if offer is None or offer.application_id != application.id:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Предложение не найдено")
    return offer


def respond(
    session: Session, user: User, application_id: UUID, offer_id: UUID, *, accept: bool
) -> Application:
    application = get_visible(session, user, application_id)
    offer = _offer_of(session, application, offer_id)
    if offer.status != OfferStatus.ACTIVE:
        raise ApiError(
            409, ErrorCode.OFFER_NOT_ACTIVE, "Предложение уже принято, отклонено или заменено"
        )
    target = ApplicationStatus.SIGNING if accept else ApplicationStatus.DECLINED_BY_CLIENT
    change_status(session, application, target, user)  # 409 invalid_transition из других статусов
    offer.status = OfferStatus.ACCEPTED if accept else OfferStatus.DECLINED
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise ApiError(
            409, ErrorCode.VERSION_CONFLICT, "Заявку уже изменили, обновите страницу"
        ) from exc
    return application

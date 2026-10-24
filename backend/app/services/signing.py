"""Подписание договора и выдача (план, раздел 4, этапы 8–9; статусы — раздел 5).

Код: SIGNING → одноразовый код по принятому офферу, новый запрос заменяет прежний.
Подтверждение: верный код → SIGNED (клиент) → ISSUED (система) в одной транзакции.

Временные правила backend (P1–P5, docs/analyst-questions.md, раздел 8) — аналитиком не подтверждены:
  * код действует 5 минут — как в моках фронта;
  * на один код — 5 попыток, дальше нужен новый код;
  * выдача синхронная: воркера пока нет, как и у конвейера после submit;
  * счёт зачисления синтетический — ****4521, как на экране C7.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.errors import ApiError
from app.db.models import Application, DisbursementRow, OfferRow, SignatureRow, User
from app.domain.state_machine import ApplicationStatus, ensure_transition
from app.schemas.applications import OfferStatus
from app.schemas.common import ErrorCode
from app.schemas.signing import SigningCodeResponse
from app.security import hash_signing_code, new_signing_code, verify_signing_code
from app.services.applications import _latest, get_visible
from app.services.status import change_status, now

CODE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 5
ACCOUNT_MASK = "****4521"

_INVALID_CODE = "Код неверный или истёк. Запросите новый код"


def _aware(moment: datetime) -> datetime:
    # SQLite (unit-тесты) возвращает время без часового пояса; в PostgreSQL оно с поясом.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _signing_application(session: Session, user: User, application_id: UUID) -> Application:
    application = get_visible(session, user, application_id)
    # 409 invalid_transition, если заявка не в SIGNING.
    ensure_transition(ApplicationStatus(application.status), ApplicationStatus.SIGNED)
    return application


def _commit(session: Session) -> None:
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise ApiError(
            409, ErrorCode.VERSION_CONFLICT, "Заявку уже изменили, обновите страницу"
        ) from exc


def create_code(session: Session, user: User, application_id: UUID) -> SigningCodeResponse:
    application = _signing_application(session, user, application_id)
    offer = _latest(session, OfferRow, application, OfferRow.status == OfferStatus.ACCEPTED)
    if offer is None:  # в SIGNING заявка попадает только через принятие оффера
        raise ApiError(409, ErrorCode.CONFLICT, "По заявке нет принятого предложения")

    pending = _latest(session, SignatureRow, application, SignatureRow.signed_at.is_(None))
    if pending is not None:
        session.delete(pending)
    code = new_signing_code()
    expires_at = now() + CODE_TTL
    session.add(
        SignatureRow(
            application_id=application.id,
            offer_id=offer.id,
            code_hash=hash_signing_code(code),
            attempts=0,
            expires_at=expires_at,
        )
    )
    session.commit()
    return SigningCodeResponse(code=code, expires_at=expires_at)


def confirm(session: Session, user: User, application_id: UUID, code: str) -> Application:
    application = _signing_application(session, user, application_id)
    signature = _latest(session, SignatureRow, application, SignatureRow.signed_at.is_(None))
    if (
        signature is None
        or signature.attempts >= MAX_ATTEMPTS
        or _aware(signature.expires_at) <= now()
    ):
        raise ApiError(422, ErrorCode.INVALID_CODE, _INVALID_CODE, field="code")
    if not verify_signing_code(code, signature.code_hash):
        signature.attempts += 1
        session.commit()
        raise ApiError(422, ErrorCode.INVALID_CODE, _INVALID_CODE, field="code")

    signature.signed_at = now()
    signature.signer_id = user.id
    change_status(session, application, ApplicationStatus.SIGNED, user)
    offer = session.get(OfferRow, signature.offer_id)
    session.add(
        DisbursementRow(
            application_id=application.id,
            offer_id=signature.offer_id,
            amount=offer.amount,
            account_mask=ACCOUNT_MASK,
            executed_at=now(),
        )
    )
    change_status(session, application, ApplicationStatus.ISSUED, None)
    _commit(session)
    return application

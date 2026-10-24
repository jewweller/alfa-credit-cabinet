"""Смена статуса заявки по машине состояний: история, событие в ленту клиента и строка
журнала действий (план, разделы 4, 5 и 10)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Application, ApplicationStatusHistory, FeedEventRow, User
from app.domain.feed_events import event_text
from app.domain.state_machine import ApplicationStatus, ensure_transition
from app.schemas.applications import StatusActor
from app.schemas.auth import UserRole
from app.services import audit


def now() -> datetime:
    return datetime.now(UTC)


def _actor_type(actor: User | None) -> StatusActor:
    if actor is None:
        return StatusActor.SYSTEM
    return StatusActor.CLIENT if actor.role == UserRole.CLIENT else StatusActor.UNDERWRITER


def add_history(
    session: Session,
    application: Application,
    from_status: ApplicationStatus | None,
    actor: User | None,
) -> None:
    """actor=None — переход выполнила система (конвейер), иначе — клиент или сотрудник банка."""
    session.add(
        ApplicationStatusHistory(
            application_id=application.id,
            from_status=from_status,
            to_status=application.status,
            actor_type=_actor_type(actor),
            actor_id=None if actor is None else actor.id,
            created_at=application.status_changed_at,
        )
    )


def change_status(
    session: Session,
    application: Application,
    to_status: ApplicationStatus,
    actor: User | None,
    audit_details: dict[str, Any] | None = None,
) -> None:
    from_status = ApplicationStatus(application.status)
    ensure_transition(from_status, to_status)
    application.status = to_status
    application.status_changed_at = now()
    add_history(session, application, from_status, actor)
    notify(session, application)
    audit.record_transition(session, application, from_status, actor, audit_details)


def notify(session: Session, application: Application) -> None:
    """Событие в ленту клиента о новом статусе — уведомление вместо email/SMS (план, раздел 4)."""
    text = event_text(ApplicationStatus(application.status), application.number)
    if text is None:
        return
    session.add(
        FeedEventRow(
            user_id=application.applicant_id,
            application_id=application.id,
            status=application.status,
            title=text[0],
            body=text[1],
            created_at=application.status_changed_at,
        )
    )

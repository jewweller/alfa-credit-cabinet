"""Смена статуса заявки по машине состояний и запись истории (план, раздел 5)."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import Application, ApplicationStatusHistory, User
from app.domain.state_machine import ApplicationStatus, ensure_transition
from app.schemas.applications import StatusActor


def now() -> datetime:
    return datetime.now(UTC)


def add_history(
    session: Session,
    application: Application,
    from_status: ApplicationStatus | None,
    actor: User | None,
) -> None:
    """actor=None — переход выполнила система (конвейер), иначе — пользователь."""
    session.add(
        ApplicationStatusHistory(
            application_id=application.id,
            from_status=from_status,
            to_status=application.status,
            actor_type=StatusActor.SYSTEM if actor is None else StatusActor.CLIENT,
            actor_id=None if actor is None else actor.id,
            created_at=application.status_changed_at,
        )
    )


def change_status(
    session: Session, application: Application, to_status: ApplicationStatus, actor: User | None
) -> None:
    from_status = ApplicationStatus(application.status)
    ensure_transition(from_status, to_status)
    application.status = to_status
    application.status_changed_at = now()
    add_history(session, application, from_status, actor)

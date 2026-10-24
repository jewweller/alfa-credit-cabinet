"""Журнал действий (план, разделы 6 и 10; схема AuditEntry, список действий — AuditAction).

Запись добавляется в ту же транзакцию, что и само действие: откатилось действие — откатилась
и строка журнала. Журнал только дописывается; сброс демо его не очищает.

Переходы статуса пишет `services.status.change_status` — по переходу понятно, что произошло
(`transition_action`). Остальные действия (черновик, файлы, код подписи, «взять в работу»,
вход, сброс) вызывающий код пишет сам через `record`.
"""

from contextvars import ContextVar
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Application, AuditLogRow, User
from app.domain.state_machine import ApplicationStatus
from app.schemas.admin import AuditAction, AuditActorRole, AuditEntry
from app.schemas.auth import UserRole

# IP клиента текущего запроса; ставит middleware в main.py. Вне запроса — None.
client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)

_SUMMARY_MAX = 200
S = ApplicationStatus


def _role(user: User | None) -> AuditActorRole:
    return AuditActorRole.SYSTEM if user is None else AuditActorRole(user.role)


def record(
    session: Session,
    action: AuditAction,
    actor: User | None,
    application: Application | None,
    summary: str,
    details: dict[str, Any] | None = None,
    *,
    actor_name: str | None = None,
    actor_role: AuditActorRole | None = None,
) -> None:
    """actor=None — система; для неудачного входа роль и имя передаются явно."""
    session.add(
        AuditLogRow(
            action=action,
            actor_role=actor_role or _role(actor),
            actor_id=actor.id if actor else None,
            actor_name=actor.full_name if actor else actor_name,
            application_id=application.id if application else None,
            application_number=application.number if application else None,
            summary=summary[:_SUMMARY_MAX],
            details=details or {},
            ip=None if actor is None and actor_role is None else client_ip.get(),
        )
    )


def transition_action(
    actor: User | None, from_status: ApplicationStatus, to_status: ApplicationStatus
) -> AuditAction:
    """Какое действие журнала означает переход статуса."""
    if actor is None:
        return AuditAction.LOAN_ISSUED if to_status == S.ISSUED else AuditAction.STATUS_CHANGED
    if actor.role != UserRole.CLIENT:
        return AuditAction.BANK_DECISION
    if to_status == S.SUBMITTED:
        if from_status == S.INFO_REQUESTED:
            return AuditAction.APPLICATION_RESUBMITTED
        return AuditAction.APPLICATION_SUBMITTED
    client_actions = {
        S.CANCELLED: AuditAction.APPLICATION_CANCELLED,
        S.SIGNING: AuditAction.OFFER_ACCEPTED,
        S.DECLINED_BY_CLIENT: AuditAction.OFFER_DECLINED,
        S.SIGNED: AuditAction.SIGNING_CONFIRMED,
    }
    return client_actions.get(to_status, AuditAction.STATUS_CHANGED)


def record_transition(
    session: Session,
    application: Application,
    from_status: ApplicationStatus,
    actor: User | None,
    details: dict[str, Any] | None = None,
) -> None:
    to_status = ApplicationStatus(application.status)
    action = transition_action(actor, from_status, to_status)
    change: dict[str, Any] = {"from_status": from_status, "to_status": to_status}
    if action == AuditAction.BANK_DECISION:
        change["outcome"] = to_status.lower()
    record(
        session,
        action,
        actor,
        application,
        f"{from_status} → {to_status}",
        {**change, **(details or {})},
    )


def entries(
    session: Session,
    application_id: UUID | None,
    actions: list[AuditAction] | None,
    actor_role: AuditActorRole | None,
    before: datetime | None,
    limit: int,
) -> list[AuditEntry]:
    """Свежие сверху; `before` — строго раньше этого момента (следующая страница)."""
    query = select(AuditLogRow)
    if application_id is not None:
        query = query.where(AuditLogRow.application_id == application_id)
    if actions:
        query = query.where(AuditLogRow.action.in_([str(a) for a in actions]))
    if actor_role is not None:
        query = query.where(AuditLogRow.actor_role == actor_role)
    if before is not None:
        query = query.where(AuditLogRow.created_at < before)
    query = query.order_by(AuditLogRow.created_at.desc(), AuditLogRow.id).limit(limit)
    return [
        AuditEntry(
            id=row.id,
            created_at=row.created_at,
            action=row.action,
            actor_role=row.actor_role,
            actor_id=row.actor_id,
            actor_name=row.actor_name,
            application_id=row.application_id,
            application_number=row.application_number,
            summary=row.summary,
            details=row.details,
            ip=row.ip,
        )
        for row in session.scalars(query)
    ]

"""Журнал действий и сброс демо-стенда (план, разделы 2, 6 и 10).

Таблица `audit_log`, операции `GET /bank/audit` и `POST /admin/demo/reset`.

Журнал только дописывается: строки не меняются и не удаляются, в том числе при сбросе демо.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import DescribedStrEnum


class AuditAction(DescribedStrEnum):
    """Что произошло. Автосохранение черновика (`PATCH`) в журнал не пишется — слишком частое."""

    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    APPLICATION_CREATED = "application.created"
    APPLICATION_SUBMITTED = "application.submitted"
    APPLICATION_RESUBMITTED = "application.resubmitted"
    APPLICATION_CANCELLED = "application.cancelled"
    STATUS_CHANGED = "application.status_changed"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_DOWNLOADED = "document.downloaded"
    OFFER_ACCEPTED = "offer.accepted"
    OFFER_DECLINED = "offer.declined"
    SIGNING_CODE_ISSUED = "signing.code_issued"
    SIGNING_CONFIRMED = "signing.confirmed"
    LOAN_ISSUED = "loan.issued"
    BANK_ASSIGNED = "bank.assigned"
    BANK_DECISION = "bank.decision"
    DEMO_RESET = "demo.reset"

    @classmethod
    def value_descriptions(cls) -> Mapping[str, str]:
        return AUDIT_ACTION_DESCRIPTIONS


AUDIT_ACTION_DESCRIPTIONS: Mapping[str, str] = {
    AuditAction.LOGIN: "вход в систему",
    AuditAction.LOGIN_FAILED: "неудачная попытка входа; `actor_name` — введённый логин",
    AuditAction.APPLICATION_CREATED: "создан черновик заявки",
    AuditAction.APPLICATION_SUBMITTED: "клиент отправил заявку",
    AuditAction.APPLICATION_RESUBMITTED: "клиент отправил заявку повторно после запроса документов",
    AuditAction.APPLICATION_CANCELLED: "клиент отменил заявку",
    AuditAction.STATUS_CHANGED: "конвейер сменил статус (обогащение, скоринг, решение движка)",
    AuditAction.DOCUMENT_UPLOADED: "клиент загрузил файл",
    AuditAction.DOCUMENT_DOWNLOADED: "кто-то открыл или скачал файл клиента",
    AuditAction.OFFER_ACCEPTED: "клиент принял предложение",
    AuditAction.OFFER_DECLINED: "клиент отказался от предложения",
    AuditAction.SIGNING_CODE_ISSUED: "выдан код подписи",
    AuditAction.SIGNING_CONFIRMED: "договор подписан",
    AuditAction.LOAN_ISSUED: "кредит выдан",
    AuditAction.BANK_ASSIGNED: "специалист взял заявку в работу",
    AuditAction.BANK_DECISION: "специалист принял решение",
    AuditAction.DEMO_RESET: "администратор сбросил демо-данные",
}


class AuditActorRole(DescribedStrEnum):
    CLIENT = "client"
    UNDERWRITER = "underwriter"
    ADMIN = "admin"
    SYSTEM = "system"

    @classmethod
    def value_descriptions(cls) -> Mapping[str, str]:
        return {
            cls.CLIENT: "клиент",
            cls.UNDERWRITER: "кредитный специалист",
            cls.ADMIN: "администратор",
            cls.SYSTEM: "система: конвейер, движок решения, выдача",
        }


class AuditEntry(BaseModel):
    """Строка журнала (таблица `audit_log`)."""

    id: UUID
    created_at: datetime
    action: AuditAction
    actor_role: AuditActorRole
    actor_id: UUID | None = Field(description="null — система или неудачный вход.")
    actor_name: str | None = Field(examples=["Дмитрий Орлов"])
    application_id: UUID | None = Field(description="Заявка, к которой относится действие.")
    application_number: str | None = Field(
        examples=["1051"], description="Номер заявки; сохраняется и после сброса демо."
    )
    summary: str = Field(
        max_length=200,
        examples=["SCORING → APPROVED"],
        description="Коротко, что изменилось: статусы, имя файла, исход решения. Формирует сервер.",
    )
    details: dict[str, Any] = Field(
        description="Подробности как есть (payload). Для отладки, интерфейс их не разбирает.",
        examples=[{"from_status": "SCORING", "to_status": "APPROVED"}],
    )
    ip: str | None = Field(examples=["172.18.0.1"])


class DemoResetResult(BaseModel):
    reset_at: datetime
    applications_deleted: int = Field(ge=0)

"""Сброс демо-стенда перед показом (план, разделы 2 и 15; операция POST /admin/demo/reset).

Удаляются все заявки и всё, что к ним относится, включая файлы в хранилище. Учётки,
компании и продукты остаются. Журнал действий не очищается: в него дописывается demo.reset.
Работает только при DEMO_MODE=true.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import get_settings
from app.db.models import (
    Application,
    ApplicationStatusHistory,
    DecisionRow,
    DisbursementRow,
    DocumentRow,
    EnrichmentResult,
    FeedEventRow,
    InfoRequestRow,
    OfferRow,
    ScoringResultRow,
    SignatureRow,
    User,
)
from app.schemas.admin import AuditAction, DemoResetResult
from app.schemas.common import ErrorCode
from app.services import audit
from app.storage import Storage

# Порядок удаления — от зависимых таблиц к заявкам (внешние ключи).
_APPLICATION_TABLES = (
    FeedEventRow,
    DisbursementRow,
    SignatureRow,
    DocumentRow,
    InfoRequestRow,
    OfferRow,
    DecisionRow,
    ScoringResultRow,
    EnrichmentResult,
    ApplicationStatusHistory,
    Application,
)


def reset_demo(session: Session, user: User, storage: Storage) -> DemoResetResult:
    if not get_settings().demo_mode:
        raise ApiError(
            409, ErrorCode.DEMO_MODE_DISABLED, "Сброс доступен только на демо-стенде (DEMO_MODE)"
        )
    deleted = session.scalar(select(func.count()).select_from(Application)) or 0
    files = list(session.scalars(select(DocumentRow.storage_path)))
    for table in _APPLICATION_TABLES:
        session.execute(delete(table))
    audit.record(
        session,
        AuditAction.DEMO_RESET,
        user,
        None,
        f"удалено заявок: {deleted}",
        {"applications_deleted": deleted},
    )
    session.commit()
    # Файлы — после коммита: если БД не сбросилась, файлы заявок остаются на месте.
    for key in files:
        storage.delete(key)
    return DemoResetResult(reset_at=datetime.now(UTC), applications_deleted=deleted)

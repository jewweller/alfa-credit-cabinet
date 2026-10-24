"""Запланированные операции API (план, раздел 10) — только описание, без реализации.

`contract_router` НЕ подключается к приложению: вызвать эти операции нельзя, они попадают
только в docs/api/openapi.json с пометкой `x-implementation-status: planned`.
При реализации операция переносится в router.py с тем же путём, методом, operation_id и схемами.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.security import HTTPBearer

from app.schemas.admin import AuditAction, AuditActorRole, AuditEntry, DemoResetResult
from app.schemas.common import ErrorResponse
from app.schemas.documents import (
    ALLOWED_UPLOAD_MIME_TYPES,
    MAX_UPLOAD_BYTES,
)

_bearer = HTTPBearer(description="JWT из `POST /api/v1/auth/login`.")
_AUTH = [Depends(_bearer)]


def _errors(**descriptions: str) -> dict[int | str, dict[str, Any]]:
    """`_errors(e401="...")` → описание ответов-ошибок в формате ErrorResponse."""
    return {
        int(key.removeprefix("e")): {"model": ErrorResponse, "description": text}
        for key, text in descriptions.items()
    }


_E401 = "Нет токена или он недействителен."
_E403_CLIENT = "Операция доступна только роли client."
_E404_APP = "Заявка не найдена. Ответ на чужую заявку (403 или 404) — TBD."
_E422 = "Ошибка валидации; `field` указывает на поле."
_E403_APP = "Нет доступа к заявке."
_E403_BANK = "Операция доступна только сотрудникам банка (роли underwriter и admin)."
_E409_TRANSITION = "`invalid_transition` — из текущего статуса операция не разрешена."

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        description="Повторный запрос с тем же ключом не создаёт дубль (план, раздел 9).",
    ),
]

contract_router = APIRouter(prefix="/api/v1")


# ── Карточка заявки (экран C5) ────────────────────────────────────────────────


_ALLOWED_TYPES = ", ".join(ALLOWED_UPLOAD_MIME_TYPES)
_MAX_MB = MAX_UPLOAD_BYTES // (1024 * 1024)


# ── Журнал и сброс демо (экраны администратора, вкладка журнала в B3) ─────────

_E403_ADMIN = "Операция доступна только роли admin."


@contract_router.get(
    "/bank/audit",
    response_model=list[AuditEntry],
    operation_id="listAuditEntries",
    tags=["bank"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401, e403=_E403_BANK, e422=_E422),
)
def list_audit_entries(
    application_id: Annotated[
        UUID | None, Query(description="Только действия по этой заявке (вкладка журнала в B3).")
    ] = None,
    action: Annotated[
        list[AuditAction] | None, Query(description="Фильтр по действиям; можно несколько.")
    ] = None,
    actor_role: Annotated[AuditActorRole | None, Query(description="Фильтр по роли.")] = None,
    before: Annotated[
        datetime | None,
        Query(description="Записи строго раньше этого момента — следующая страница."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Сколько записей вернуть.")] = 100,
) -> None:
    """Журнал действий (план, раздел 10), свежие сверху. Читают underwriter и admin."""


@contract_router.post(
    "/admin/demo/reset",
    response_model=DemoResetResult,
    operation_id="resetDemo",
    tags=["admin"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_ADMIN,
        e409="`demo_mode_disabled` — стенд запущен без `DEMO_MODE=true`.",
    ),
)
def reset_demo() -> None:
    """Сбросить демо-данные перед показом (план, раздел 15).

    Удаляет все заявки со всем, что к ним относится: документы и файлы, офферы, решения,
    историю статусов, подписи, выдачи, события ленты. Учётки, компании и продукты остаются.
    Журнал не очищается: в него дописывается `demo.reset`. Повторный вызов безопасен.
    """

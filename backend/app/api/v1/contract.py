"""Запланированные операции API (план, раздел 10) — только описание, без реализации.

`contract_router` НЕ подключается к приложению: вызвать эти операции нельзя, они попадают
только в docs/api/openapi.json с пометкой `x-implementation-status: planned`.
При реализации операция переносится в router.py с тем же путём, методом, operation_id и схемами.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.security import HTTPBearer

from app.schemas.common import ErrorResponse
from app.schemas.documents import (
    ALLOWED_UPLOAD_MIME_TYPES,
    MAX_UPLOAD_BYTES,
)
from app.schemas.feed import FeedItemKind, FeedResponse

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


# ── Лента (экраны C2, C8) ─────────────────────────────────────────────────────


@contract_router.get(
    "/feed",
    response_model=FeedResponse,
    operation_id="getFeed",
    tags=["feed"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401, e403=_E403_CLIENT, e422=_E422),
)
def get_feed(
    kind: Annotated[
        FeedItemKind | None,
        Query(description="Только события или только новости (фильтр C8). Без фильтра — всё."),
    ] = None,
    news_limit: Annotated[
        int, Query(ge=1, le=30, description="Сколько новостей вернуть, лучших по весу.")
    ] = 10,
) -> None:
    """Персональная лента клиента (план, раздел 11).

    Сверху все события по заявкам клиента, свежие первыми. Ниже — новости из `seed/news.json`
    по убыванию веса. Вес — по формуле плана или моделью ML (`ranking.method`), при сбое
    модели — по формуле. У каждой новости есть `reasons` — строка «Почему вы это видите».
    """


@contract_router.post(
    "/feed/events/{id}/read",
    status_code=204,
    operation_id="markFeedEventRead",
    tags=["feed"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_CLIENT,
        e404="Событие не найдено или принадлежит другому клиенту.",
    ),
)
def mark_feed_event_read(id: UUID) -> None:
    """Отметить событие прочитанным. Повторный вызов ничего не меняет."""

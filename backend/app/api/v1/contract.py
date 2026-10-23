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
from app.schemas.products import ProductRecommendation, ProductRecommendRequest
from app.schemas.schedule import PaymentSchedule

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
_E409_TRANSITION = "`invalid_transition` — из текущего статуса операция не разрешена."

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        description="Повторный запрос с тем же ключом не создаёт дубль (план, раздел 9).",
    ),
]

contract_router = APIRouter(prefix="/api/v1")


@contract_router.post(
    "/products/recommend",
    response_model=list[ProductRecommendation],
    operation_id="recommendProducts",
    tags=["products"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401, e422=_E422),
)
def recommend_products(body: ProductRecommendRequest) -> None:
    """Подбор продукта по цели, сумме и сроку (экран C3).

    Возвращает 0–3 продукта, у которых цель есть в `purpose_tags`. Сначала те, что подходят
    без изменений, затем с меньшим платежом. Пустой список — под эту цель продуктов нет.
    """


# ── Карточка заявки (экран C5) ────────────────────────────────────────────────


@contract_router.get(
    "/applications/{id}/schedule",
    response_model=PaymentSchedule,
    operation_id="getPaymentSchedule",
    tags=["offers"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_APP,
        e404="Заявка не найдена или по ней нет оффера.",
        e422=_E422,
    ),
)
def get_payment_schedule(
    id: UUID,
    offer_id: Annotated[
        UUID | None,
        Query(description="Какой оффер. По умолчанию — активный, после принятия — принятый."),
    ] = None,
) -> None:
    """График платежей по офферу: для сравнения «просили / предлагаем» и экрана выдачи."""


_ALLOWED_TYPES = ", ".join(ALLOWED_UPLOAD_MIME_TYPES)
_MAX_MB = MAX_UPLOAD_BYTES // (1024 * 1024)

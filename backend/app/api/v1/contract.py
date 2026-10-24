"""Запланированные операции API (план, раздел 10) — только описание, без реализации.

`contract_router` НЕ подключается к приложению: вызвать эти операции нельзя, они попадают
только в docs/api/openapi.json с пометкой `x-implementation-status: planned`.
При реализации операция переносится в router.py с тем же путём, методом, operation_id и схемами.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.security import HTTPBearer

from app.domain.state_machine import ApplicationStatus
from app.schemas.bank import (
    BankApplicationDetail,
    BankApplicationSummary,
    Grade,
    UnderwriterDecisionRequest,
)
from app.schemas.common import ErrorResponse
from app.schemas.documents import (
    ALLOWED_UPLOAD_MIME_TYPES,
    MAX_UPLOAD_BYTES,
)
from app.schemas.products import ProductRecommendation, ProductRecommendRequest

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


_ALLOWED_TYPES = ", ".join(ALLOWED_UPLOAD_MIME_TYPES)
_MAX_MB = MAX_UPLOAD_BYTES // (1024 * 1024)


# ── Кабинет банка (экраны B2–B4) ──────────────────────────────────────────────


@contract_router.get(
    "/bank/applications",
    response_model=list[BankApplicationSummary],
    operation_id="listBankApplications",
    tags=["bank"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401, e403=_E403_BANK, e422=_E422),
)
def list_bank_applications(
    status: Annotated[
        list[ApplicationStatus] | None,
        Query(description="Фильтр по статусам; можно несколько. Без фильтра — все, кроме DRAFT."),
    ] = None,
    grade: Annotated[Grade | None, Query(description="Фильтр по грейду.")] = None,
    product_id: Annotated[UUID | None, Query(description="Фильтр по продукту.")] = None,
) -> None:
    """Очередь заявок всех клиентов (экран B2).

    Черновики (`DRAFT`) банку не видны. Сортировка: сначала `MANUAL_REVIEW`, внутри — дольше
    всего ждущие (по `status_changed_at`), затем остальные, свежие сверху.
    """


@contract_router.get(
    "/bank/applications/{id}",
    response_model=BankApplicationDetail,
    operation_id="getBankApplication",
    tags=["bank"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401, e403=_E403_BANK, e404=_E404_APP),
)
def get_bank_application(id: UUID) -> None:
    """Полная карточка для андеррайтера (экран B3): анкета, источники, скоринг, правила, решение."""


@contract_router.post(
    "/bank/applications/{id}/assign",
    response_model=BankApplicationDetail,
    operation_id="assignBankApplication",
    tags=["bank"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_BANK,
        e404=_E404_APP,
        e409=(
            f"{_E409_TRANSITION} Взять в работу можно только заявку в `MANUAL_REVIEW`. "
            "`assigned_to_other` — заявку уже ведёт другой специалист."
        ),
    ),
)
def assign_bank_application(id: UUID) -> None:
    """Взять заявку в работу. Повторный вызов тем же специалистом ничего не меняет."""


@contract_router.post(
    "/bank/applications/{id}/decision",
    response_model=BankApplicationDetail,
    operation_id="decideBankApplication",
    tags=["bank"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_BANK,
        e404=_E404_APP,
        e409=(
            f"{_E409_TRANSITION} Решение принимается только в `MANUAL_REVIEW`. "
            "`assigned_to_other` — заявку ведёт другой специалист; сначала её нужно взять в работу."
        ),
        e422=(
            "Ошибка валидации: для выбранного `outcome` не хватает полей "
            "или условия вне лимитов продукта."
        ),
    ),
)
def decide_bank_application(
    id: UUID, body: UnderwriterDecisionRequest, idempotency_key: IdempotencyKey = None
) -> None:
    """Решение специалиста (экран B4): `MANUAL_REVIEW` → одобрение, другие условия, запрос
    документов или отказ. Клиент видит итог в карточке заявки и событие в ленте."""

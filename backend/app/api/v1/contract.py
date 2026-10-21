"""Контракт первой волны API (план, раздел 10) — только описание, без реализации.

`contract_router` НЕ подключается к приложению: вызвать эти операции нельзя, они попадают
только в docs/api/openapi.json с пометкой `x-implementation-status: planned`.
При реализации операция переносится в router.py с тем же путём, методом, operation_id и схемами.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.security import HTTPBearer

from app.schemas.applications import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    ApplicationUpdate,
)
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse
from app.schemas.common import INN_PATTERN, ErrorResponse
from app.schemas.companies import CompanyLookupResponse
from app.schemas.products import Product

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

contract_router = APIRouter(prefix="/api/v1")


@contract_router.post(
    "/auth/login",
    response_model=TokenResponse,
    operation_id="login",
    tags=["auth"],
    responses=_errors(e401="Неверный email или пароль.", e422=_E422),
)
def login(body: LoginRequest) -> None:
    """Вход по email и паролю, выдаёт JWT."""


@contract_router.get(
    "/auth/me",
    response_model=MeResponse,
    operation_id="getMe",
    tags=["auth"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401),
)
def get_me() -> None:
    """Текущий пользователь, роль и компания."""


@contract_router.get(
    "/products",
    response_model=list[Product],
    operation_id="listProducts",
    tags=["products"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401),
)
def list_products() -> None:
    """Каталог кредитных продуктов."""


@contract_router.get(
    "/companies/lookup",
    response_model=CompanyLookupResponse,
    operation_id="lookupCompany",
    tags=["companies"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e404="Компания не найдена в реестре (`company_not_found`).",
        e422="ИНН не из 10 или 12 цифр.",
        e503="Реестр недоступен (`upstream_unavailable`). Предварительно, TBD.",
    ),
)
def lookup_company(
    inn: Annotated[str, Query(pattern=INN_PATTERN, description="ИНН: 10 цифр (ООО) или 12 (ИП).")],
) -> None:
    """Автозаполнение из ЕГРЮЛ (10 цифр) или ЕГРИП (12 цифр) через сервис моков."""


@contract_router.get(
    "/applications",
    response_model=list[ApplicationSummary],
    operation_id="listApplications",
    tags=["applications"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401),
)
def list_applications() -> None:
    """Заявки компании текущего клиента."""


@contract_router.post(
    "/applications",
    response_model=ApplicationDetail,
    status_code=status.HTTP_201_CREATED,
    operation_id="createApplication",
    tags=["applications"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401, e403=_E403_CLIENT, e422=_E422),
)
def create_application(body: ApplicationCreate) -> None:
    """Создать черновик заявки в статусе `DRAFT`."""


@contract_router.get(
    "/applications/{id}",
    response_model=ApplicationDetail,
    operation_id="getApplication",
    tags=["applications"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401, e403="Нет доступа к заявке.", e404=_E404_APP, e422=_E422),
)
def get_application(id: UUID) -> None:
    """Заявка, статус и активный оффер. Фронт опрашивает каждые 3 секунды (план, раздел 5)."""


@contract_router.patch(
    "/applications/{id}",
    response_model=ApplicationDetail,
    operation_id="updateApplication",
    tags=["applications"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403="Нет доступа к заявке.",
        e404=_E404_APP,
        e409="`version_conflict` — заявку уже изменили; или статус не позволяет изменение (TBD).",
        e422=_E422,
    ),
)
def update_application(id: UUID, body: ApplicationUpdate) -> None:
    """Автосохранение черновика."""


@contract_router.post(
    "/applications/{id}/submit",
    response_model=ApplicationDetail,
    operation_id="submitApplication",
    tags=["applications"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403="Нет доступа к заявке.",
        e404=_E404_APP,
        e409="`invalid_transition` — из текущего статуса отправка не разрешена.",
        e422=(
            "Проверка полноты не прошла: обязательные поля, контрольная сумма ИНН, "
            "лимиты продукта (план, раздел 4, этап 2). `field` указывает на поле."
        ),
    ),
)
def submit_application(
    id: UUID,
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Повторный запрос с тем же ключом не создаёт дубль (план, раздел 9).",
        ),
    ] = None,
) -> None:
    """Проверка полноты и отправка: `DRAFT` → `SUBMITTED`."""

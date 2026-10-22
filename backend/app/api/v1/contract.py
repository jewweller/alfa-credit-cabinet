"""Контракт первой волны API (план, раздел 10) — только описание, без реализации.

`contract_router` НЕ подключается к приложению: вызвать эти операции нельзя, они попадают
только в docs/api/openapi.json с пометкой `x-implementation-status: planned`.
При реализации операция переносится в router.py с тем же путём, методом, operation_id и схемами.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status
from fastapi.security import HTTPBearer

from app.schemas.applications import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    ApplicationUpdate,
    StatusHistoryEntry,
)
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse
from app.schemas.common import INN_PATTERN, ErrorResponse
from app.schemas.companies import CompanyLookupResponse
from app.schemas.documents import (
    ALLOWED_UPLOAD_MIME_TYPES,
    MAX_UPLOAD_BYTES,
    DocumentInfo,
    DocumentKind,
)
from app.schemas.products import Product
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
def submit_application(id: UUID, idempotency_key: IdempotencyKey = None) -> None:
    """Проверка полноты и отправка: `DRAFT` → `SUBMITTED`."""


# ── Карточка заявки (экран C5) ────────────────────────────────────────────────


@contract_router.get(
    "/applications/{id}/history",
    response_model=list[StatusHistoryEntry],
    operation_id="getApplicationHistory",
    tags=["applications"],
    dependencies=_AUTH,
    responses=_errors(e401=_E401, e403=_E403_APP, e404=_E404_APP, e422=_E422),
)
def get_application_history(id: UUID) -> None:
    """Таймлайн статусов заявки, от старых к новым."""


@contract_router.post(
    "/applications/{id}/offers/{offer_id}/accept",
    response_model=ApplicationDetail,
    operation_id="acceptOffer",
    tags=["offers"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_APP,
        e404="Заявка или оффер не найдены.",
        e409=f"{_E409_TRANSITION} `offer_not_active` — оффер уже принят, отклонён или заменён.",
        e422=_E422,
    ),
)
def accept_offer(id: UUID, offer_id: UUID, idempotency_key: IdempotencyKey = None) -> None:
    """Принять оффер: `APPROVED` / `COUNTER_OFFER` → `SIGNING`."""


@contract_router.post(
    "/applications/{id}/offers/{offer_id}/decline",
    response_model=ApplicationDetail,
    operation_id="declineOffer",
    tags=["offers"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_APP,
        e404="Заявка или оффер не найдены.",
        e409=f"{_E409_TRANSITION} `offer_not_active` — оффер уже принят, отклонён или заменён.",
        e422=_E422,
    ),
)
def decline_offer(id: UUID, offer_id: UUID, idempotency_key: IdempotencyKey = None) -> None:
    """Отказаться от оффера: `APPROVED` / `COUNTER_OFFER` → `DECLINED_BY_CLIENT`."""


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


@contract_router.post(
    "/applications/{id}/documents",
    response_model=DocumentInfo,
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadDocument",
    tags=["documents"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_APP,
        e404=_E404_APP,
        e409="Загрузка разрешена только в `INFO_REQUESTED` (в `DRAFT` — TBD).",
        e413=f"`file_too_large` — файл больше {_MAX_MB} МБ.",
        e415=f"`unsupported_media_type` — допустимы только {_ALLOWED_TYPES}.",
        e422=_E422,
    ),
)
def upload_document(
    id: UUID,
    file: Annotated[UploadFile, File(description=f"PDF, JPG или PNG до {_MAX_MB} МБ.")],
    kind: Annotated[DocumentKind, Form(description="Тип документа.")],
    info_request_id: Annotated[
        UUID | None, Form(description="Ответом на какой запрос банка загружается файл.")
    ] = None,
) -> None:
    """Загрузить файл в заявку. На диске имя — UUID, хранится sha256 (план, раздел 9)."""


@contract_router.get(
    "/documents/{id}",
    response_class=Response,
    operation_id="downloadDocument",
    tags=["documents"],
    dependencies=_AUTH,
    responses={
        200: {
            "description": "Файл с исходным именем в `Content-Disposition`.",
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in ALLOWED_UPLOAD_MIME_TYPES
            },
        },
        **_errors(
            e401=_E401,
            e403="Файл из чужой заявки.",
            e404="Файл не найден.",
            e422=_E422,
        ),
    },
)
def download_document(id: UUID) -> None:
    """Скачать файл: клиент — из своих заявок, андеррайтер — из любых."""


@contract_router.post(
    "/applications/{id}/resubmit",
    response_model=ApplicationDetail,
    operation_id="resubmitApplication",
    tags=["applications"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401,
        e403=_E403_APP,
        e404=_E404_APP,
        e409=_E409_TRANSITION,
        e422="`documents_required` — не загружены обязательные документы из запроса банка.",
    ),
)
def resubmit_application(id: UUID, idempotency_key: IdempotencyKey = None) -> None:
    """Ответить на запрос документов: `INFO_REQUESTED` → `SUBMITTED`, конвейер идёт заново."""


@contract_router.post(
    "/applications/{id}/cancel",
    response_model=ApplicationDetail,
    operation_id="cancelApplication",
    tags=["applications"],
    dependencies=_AUTH,
    responses=_errors(
        e401=_E401, e403=_E403_APP, e404=_E404_APP, e409=_E409_TRANSITION, e422=_E422
    ),
)
def cancel_application(id: UUID, idempotency_key: IdempotencyKey = None) -> None:
    """Отозвать заявку: `DRAFT` / `INFO_REQUESTED` → `CANCELLED`."""

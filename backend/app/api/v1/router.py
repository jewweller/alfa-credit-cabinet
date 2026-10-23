"""Реализованные эндпоинты `/api/v1`. Сюда переносятся операции из contract.py.

Путь, метод, operation_id, схемы и описания ошибок переносятся без изменений: фронтенд
сгенерировал клиент по контракту, меняется только `x-implementation-status`.
"""

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select

from app.api.deps import ClientUser, CurrentUser, SessionDep
from app.api.v1.contract import (
    _ALLOWED_TYPES,
    _E401,
    _E403_APP,
    _E403_CLIENT,
    _E404_APP,
    _E409_TRANSITION,
    _E422,
    _MAX_MB,
    IdempotencyKey,
    _errors,
)
from app.db.models import Product as ProductRow
from app.db.models import User
from app.integrations.base import SourceClient
from app.integrations.fixtures import get_source_client
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    ApplicationUpdate,
    StatusHistoryEntry,
)
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse
from app.schemas.common import INN_PATTERN
from app.schemas.companies import CompanyBrief, CompanyLookupResponse
from app.schemas.documents import ALLOWED_UPLOAD_MIME_TYPES, DocumentInfo, DocumentKind
from app.schemas.products import Product
from app.security import create_access_token, verify_password
from app.services import applications as service
from app.services import companies, documents, offers
from app.storage import Storage, get_storage

api_v1_router = APIRouter(prefix="/api/v1")


@api_v1_router.get("/health", tags=["system"], operation_id="health")
def health() -> dict[str, str]:
    """Живость API (план, раздел 10). Корневой `/health` остаётся для Docker healthcheck."""
    return {"status": "ok"}


# ── Вход ──────────────────────────────────────────────────────────────────────


@api_v1_router.post(
    "/auth/login",
    response_model=TokenResponse,
    operation_id="login",
    tags=["auth"],
    responses=_errors(e401="Неверный email или пароль.", e422=_E422),
)
def login(body: LoginRequest, session: SessionDep) -> TokenResponse:
    """Вход по email и паролю, выдаёт JWT."""
    user = session.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    # verify_password вызывается и для несуществующего email, чтобы время ответа не отличалось.
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        raise HTTPException(401, "Неверный email или пароль")
    return TokenResponse(access_token=create_access_token(user.id, user.role))


@api_v1_router.get(
    "/auth/me",
    response_model=MeResponse,
    operation_id="getMe",
    tags=["auth"],
    responses=_errors(e401=_E401),
)
def get_me(user: CurrentUser) -> MeResponse:
    """Текущий пользователь, роль и компания."""
    company = user.company
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        company=CompanyBrief(
            id=company.id,
            inn=company.inn,
            name=company.name,
            kind=company.kind,
            okved_main=company.okved_main,
            segment=company.segment,
        )
        if company
        else None,
    )


# ── Каталог ───────────────────────────────────────────────────────────────────


@api_v1_router.get(
    "/products",
    response_model=list[Product],
    operation_id="listProducts",
    tags=["products"],
    responses=_errors(e401=_E401),
)
def list_products(_: CurrentUser, session: SessionDep) -> list[Product]:
    """Каталог кредитных продуктов."""
    rows = session.scalars(select(ProductRow).order_by(ProductRow.code))
    return [
        Product(
            id=row.id,
            code=row.code,
            name=row.name,
            purpose_tags=row.purpose_tags,
            min_amount=row.min_amount,
            max_amount=row.max_amount,
            min_term=row.min_term,
            max_term=row.max_term,
            base_rate=row.base_rate,
        )
        for row in rows
    ]


# ── Автозаполнение компании ───────────────────────────────────────────────────

Sources = Annotated[SourceClient, Depends(get_source_client)]


@api_v1_router.get(
    "/companies/lookup",
    response_model=CompanyLookupResponse,
    operation_id="lookupCompany",
    tags=["companies"],
    responses=_errors(
        e401=_E401,
        e404="Компания не найдена в реестре (`company_not_found`).",
        e422="ИНН не из 10 или 12 цифр.",
        e503="Реестр недоступен (`upstream_unavailable`). Предварительно, TBD.",
    ),
)
def lookup_company(
    inn: Annotated[str, Query(pattern=INN_PATTERN, description="ИНН: 10 цифр (ООО) или 12 (ИП).")],
    _: CurrentUser,
    sources: Sources,
) -> CompanyLookupResponse:
    """Автозаполнение из ЕГРЮЛ (10 цифр) или ЕГРИП (12 цифр) через сервис моков."""
    return companies.lookup(sources, inn)


# ── Заявки ────────────────────────────────────────────────────────────────────


@api_v1_router.get(
    "/applications",
    response_model=list[ApplicationSummary],
    operation_id="listApplications",
    tags=["applications"],
    responses=_errors(e401=_E401),
)
def list_applications(user: ClientUser, session: SessionDep) -> list[ApplicationSummary]:
    """Заявки компании текущего клиента."""
    return [service.to_summary(session, a) for a in service.list_for_client(session, user)]


@api_v1_router.post(
    "/applications",
    response_model=ApplicationDetail,
    status_code=status.HTTP_201_CREATED,
    operation_id="createApplication",
    tags=["applications"],
    responses=_errors(e401=_E401, e403=_E403_CLIENT, e422=_E422),
)
def create_application(
    body: ApplicationCreate, user: ClientUser, session: SessionDep
) -> ApplicationDetail:
    """Создать черновик заявки в статусе `DRAFT`."""
    return service.to_detail(session, service.create_draft(session, user, body))


@api_v1_router.get(
    "/applications/{id}",
    response_model=ApplicationDetail,
    operation_id="getApplication",
    tags=["applications"],
    responses=_errors(e401=_E401, e403="Нет доступа к заявке.", e404=_E404_APP, e422=_E422),
)
def get_application(id: UUID, user: ClientUser, session: SessionDep) -> ApplicationDetail:
    """Заявка, статус и активный оффер. Фронт опрашивает каждые 3 секунды (план, раздел 5)."""
    return service.to_detail(session, service.get_visible(session, user, id))


@api_v1_router.patch(
    "/applications/{id}",
    response_model=ApplicationDetail,
    operation_id="updateApplication",
    tags=["applications"],
    responses=_errors(
        e401=_E401,
        e403="Нет доступа к заявке.",
        e404=_E404_APP,
        e409="`version_conflict` — заявку уже изменили; или статус не позволяет изменение (TBD).",
        e422=_E422,
    ),
)
def update_application(
    id: UUID, body: ApplicationUpdate, user: ClientUser, session: SessionDep
) -> ApplicationDetail:
    """Автосохранение черновика."""
    return service.to_detail(session, service.update_draft(session, user, id, body))


@api_v1_router.post(
    "/applications/{id}/submit",
    response_model=ApplicationDetail,
    operation_id="submitApplication",
    tags=["applications"],
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
    user: ClientUser,
    session: SessionDep,
    sources: Sources,
    idempotency_key: IdempotencyKey = None,
) -> ApplicationDetail:
    """Проверка полноты и отправка: `DRAFT` → `SUBMITTED`."""
    return service.to_detail(session, service.submit(session, user, id, sources))


@api_v1_router.get(
    "/applications/{id}/history",
    response_model=list[StatusHistoryEntry],
    operation_id="getApplicationHistory",
    tags=["applications"],
    responses=_errors(e401=_E401, e403=_E403_APP, e404=_E404_APP, e422=_E422),
)
def get_application_history(
    id: UUID, user: CurrentUser, session: SessionDep
) -> list[StatusHistoryEntry]:
    """Таймлайн статусов заявки, от старых к новым."""
    return service.history(session, user, id)


@api_v1_router.post(
    "/applications/{id}/cancel",
    response_model=ApplicationDetail,
    operation_id="cancelApplication",
    tags=["applications"],
    responses=_errors(
        e401=_E401, e403=_E403_APP, e404=_E404_APP, e409=_E409_TRANSITION, e422=_E422
    ),
)
def cancel_application(
    id: UUID, user: ClientUser, session: SessionDep, idempotency_key: IdempotencyKey = None
) -> ApplicationDetail:
    """Отозвать заявку: `DRAFT` / `INFO_REQUESTED` → `CANCELLED`."""
    return service.to_detail(session, service.cancel(session, user, id))


# ── Ответ на оффер ────────────────────────────────────────────────────────────

_E409_OFFER = f"{_E409_TRANSITION} `offer_not_active` — оффер уже принят, отклонён или заменён."


@api_v1_router.post(
    "/applications/{id}/offers/{offer_id}/accept",
    response_model=ApplicationDetail,
    operation_id="acceptOffer",
    tags=["offers"],
    responses=_errors(
        e401=_E401,
        e403=_E403_APP,
        e404="Заявка или оффер не найдены.",
        e409=_E409_OFFER,
        e422=_E422,
    ),
)
def accept_offer(
    id: UUID,
    offer_id: UUID,
    user: ClientUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey = None,
) -> ApplicationDetail:
    """Принять оффер: `APPROVED` / `COUNTER_OFFER` → `SIGNING`."""
    return service.to_detail(session, offers.respond(session, user, id, offer_id, accept=True))


@api_v1_router.post(
    "/applications/{id}/offers/{offer_id}/decline",
    response_model=ApplicationDetail,
    operation_id="declineOffer",
    tags=["offers"],
    responses=_errors(
        e401=_E401,
        e403=_E403_APP,
        e404="Заявка или оффер не найдены.",
        e409=_E409_OFFER,
        e422=_E422,
    ),
)
def decline_offer(
    id: UUID,
    offer_id: UUID,
    user: ClientUser,
    session: SessionDep,
    idempotency_key: IdempotencyKey = None,
) -> ApplicationDetail:
    """Отказаться от оффера: `APPROVED` / `COUNTER_OFFER` → `DECLINED_BY_CLIENT`."""
    return service.to_detail(session, offers.respond(session, user, id, offer_id, accept=False))


# ── Документы и ответ на запрос банка ─────────────────────────────────────────

Files = Annotated[Storage, Depends(get_storage)]


@api_v1_router.post(
    "/applications/{id}/documents",
    response_model=DocumentInfo,
    status_code=status.HTTP_201_CREATED,
    operation_id="uploadDocument",
    tags=["documents"],
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
    user: ClientUser,
    session: SessionDep,
    storage: Files,
    info_request_id: Annotated[
        UUID | None, Form(description="Ответом на какой запрос банка загружается файл.")
    ] = None,
) -> DocumentInfo:
    """Загрузить файл в заявку. На диске имя — UUID, хранится sha256 (план, раздел 9)."""
    document = documents.upload(session, user, id, file, kind, info_request_id, storage)
    return service.to_document_info(document)


@api_v1_router.get(
    "/documents/{id}",
    response_class=Response,
    operation_id="downloadDocument",
    tags=["documents"],
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
def download_document(id: UUID, user: CurrentUser, session: SessionDep, storage: Files) -> Response:
    """Скачать файл: клиент — из своих заявок, андеррайтер — из любых."""
    document, content = documents.download(session, user, id, storage)
    return Response(
        content=content,
        media_type=document.mime,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename)}"},
    )


@api_v1_router.post(
    "/applications/{id}/resubmit",
    response_model=ApplicationDetail,
    operation_id="resubmitApplication",
    tags=["applications"],
    responses=_errors(
        e401=_E401,
        e403=_E403_APP,
        e404=_E404_APP,
        e409=_E409_TRANSITION,
        e422="`documents_required` — не загружены обязательные документы из запроса банка.",
    ),
)
def resubmit_application(
    id: UUID,
    user: ClientUser,
    session: SessionDep,
    sources: Sources,
    idempotency_key: IdempotencyKey = None,
) -> ApplicationDetail:
    """Ответить на запрос документов: `INFO_REQUESTED` → `SUBMITTED`, конвейер идёт заново."""
    return service.to_detail(session, service.resubmit(session, user, id, sources))

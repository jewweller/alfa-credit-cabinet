"""Реализованные эндпоинты `/api/v1`. Сюда переносятся операции из contract.py.

Путь, метод, operation_id, схемы и описания ошибок переносятся без изменений: фронтенд
сгенерировал клиент по контракту, меняется только `x-implementation-status`.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import ClientUser, CurrentUser, SessionDep
from app.api.v1.contract import (
    _E401,
    _E403_APP,
    _E403_CLIENT,
    _E404_APP,
    _E422,
    IdempotencyKey,
    _errors,
)
from app.db.models import Product as ProductRow
from app.db.models import User
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    ApplicationUpdate,
    StatusHistoryEntry,
)
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse
from app.schemas.companies import CompanyBrief
from app.schemas.products import Product
from app.security import create_access_token, verify_password
from app.services import applications as service

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
    return [service.to_summary(a) for a in service.list_for_client(session, user)]


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
    return service.to_detail(service.create_draft(session, user, body))


@api_v1_router.get(
    "/applications/{id}",
    response_model=ApplicationDetail,
    operation_id="getApplication",
    tags=["applications"],
    responses=_errors(e401=_E401, e403="Нет доступа к заявке.", e404=_E404_APP, e422=_E422),
)
def get_application(id: UUID, user: ClientUser, session: SessionDep) -> ApplicationDetail:
    """Заявка, статус и активный оффер. Фронт опрашивает каждые 3 секунды (план, раздел 5)."""
    return service.to_detail(service.get_visible(session, user, id))


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
    return service.to_detail(service.update_draft(session, user, id, body))


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
    id: UUID, user: ClientUser, session: SessionDep, idempotency_key: IdempotencyKey = None
) -> ApplicationDetail:
    """Проверка полноты и отправка: `DRAFT` → `SUBMITTED`."""
    return service.to_detail(service.submit(session, user, id))


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

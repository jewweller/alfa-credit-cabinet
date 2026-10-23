"""Черновик заявки, отправка и то, что видит клиент (план, раздел 4; статусы — раздел 5).

`submit` сразу обрабатывает заявку (services/pipeline.py): обогащение, скоринг, решение —
синхронно, в одной транзакции с отправкой. Файлов у заявок пока не бывает.
"""

from uuid import UUID

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.errors import ApiError
from app.db.models import (
    Application,
    ApplicationStatusHistory,
    DecisionRow,
    InfoRequestRow,
    OfferRow,
    Product,
    User,
)
from app.domain.inn import is_valid_inn
from app.domain.state_machine import ApplicationStatus, InvalidTransitionError
from app.integrations.base import SourceClient
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationSummary,
    ApplicationUpdate,
    Offer,
    StatusHistoryEntry,
)
from app.schemas.auth import UserRole
from app.schemas.common import ErrorCode
from app.schemas.decisions import ClientDecision, DecisionOutcome
from app.schemas.documents import InfoRequest, InfoRequestItem
from app.services.pipeline import process_submitted
from app.services.status import add_history, change_status, now

_NUMBER_ATTEMPTS = 3


def _not_found() -> ApiError:
    # TBD (вопрос A2): чужая заявка — 403 или 404. Пока 404: не раскрываем, что она существует.
    return ApiError(404, ErrorCode.NOT_FOUND, "Заявка не найдена")


def _invalid(field: str, message: str) -> ApiError:
    return ApiError(422, ErrorCode.VALIDATION_ERROR, message, field)


def _next_number(session: Session) -> str:
    # TBD (вопрос A4): формат номера не определён. Пока сквозной счётчик из 4+ цифр, как в моках.
    last = session.scalar(select(func.max(cast(Application.number, Integer))))
    return f"{(last or 0) + 1:04d}"


def _check_product(session: Session, product_id: UUID | None) -> None:
    if product_id is not None and session.get(Product, product_id) is None:
        raise _invalid("product_id", "Такого продукта нет")


def get_visible(session: Session, user: User, application_id: UUID) -> Application:
    """Клиент видит заявки своей компании; андеррайтер — любые (план, раздел 9)."""
    application = session.get(Application, application_id)
    if application is None:
        raise _not_found()
    if user.role == UserRole.UNDERWRITER:
        return application
    if user.role == UserRole.CLIENT and application.company_id == user.company_id:
        return application
    raise _not_found()


def list_for_client(session: Session, user: User) -> list[Application]:
    query = (
        select(Application)
        .where(Application.company_id == user.company_id)
        .order_by(Application.created_at.desc())
    )
    return list(session.scalars(query))


def create_draft(session: Session, user: User, data: ApplicationCreate) -> Application:
    _check_product(session, data.product_id)
    for attempt in range(_NUMBER_ATTEMPTS):
        application = Application(
            number=_next_number(session),
            company_id=user.company_id,
            applicant_id=user.id,
            product_id=data.product_id,
            amount=data.amount,
            term_months=data.term_months,
            purpose=data.purpose,
            bki_consent=False,
            status=ApplicationStatus.DRAFT,
            status_changed_at=now(),
        )
        session.add(application)
        try:
            session.flush()
        except IntegrityError:  # номер занят параллельным запросом — берём следующий
            session.rollback()
            if attempt == _NUMBER_ATTEMPTS - 1:
                raise
            continue
        add_history(session, application, None, user)
        session.commit()
        return application
    raise AssertionError("unreachable")


def update_draft(
    session: Session, user: User, application_id: UUID, data: ApplicationUpdate
) -> Application:
    application = get_visible(session, user, application_id)
    if data.version != application.version:
        raise ApiError(409, ErrorCode.VERSION_CONFLICT, "Заявку уже изменили, обновите страницу")
    if application.status != ApplicationStatus.DRAFT:
        # TBD (вопрос A3): разрешать ли изменения в INFO_REQUESTED. Пока — только черновик.
        raise ApiError(409, ErrorCode.CONFLICT, "Изменять можно только черновик")

    changes = data.model_dump(exclude_unset=True, exclude={"version"})
    if "product_id" in changes:
        _check_product(session, changes["product_id"])
    for field, value in changes.items():
        setattr(application, field, value)
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise ApiError(
            409, ErrorCode.VERSION_CONFLICT, "Заявку уже изменили, обновите страницу"
        ) from exc
    return application


def _validate_for_submit(application: Application) -> None:
    """Проверка полноты и корректности (план, раздел 4, этап 2)."""
    required = [
        ("product_id", "Выберите продукт"),
        ("amount", "Укажите сумму кредита"),
        ("term_months", "Укажите срок кредита"),
        ("purpose", "Укажите цель кредита"),
        ("revenue_12m", "Укажите выручку за 12 месяцев"),
        (
            "existing_payments_monthly",
            "Укажите текущие платежи по кредитам в месяц (0, если их нет)",
        ),
    ]
    for field, message in required:
        if getattr(application, field) is None:
            raise _invalid(field, message)
    if not application.bki_consent:
        raise _invalid("bki_consent", "Нужно согласие на запрос в бюро кредитных историй")
    if not is_valid_inn(application.company.inn):
        raise _invalid("inn", "ИНН компании не прошёл проверку контрольной суммы")

    product = application.product
    assert product is not None and application.amount is not None
    if not product.min_amount <= application.amount <= product.max_amount:
        raise _invalid(
            "amount",
            f"Сумма для продукта «{product.name}» — от {product.min_amount:,.0f} "
            f"до {product.max_amount:,.0f} ₽".replace(",", " "),
        )
    assert application.term_months is not None
    if not product.min_term <= application.term_months <= product.max_term:
        raise _invalid(
            "term_months",
            f"Срок для продукта «{product.name}» — от {product.min_term} "
            f"до {product.max_term} мес.",
        )


def submit(
    session: Session, user: User, application_id: UUID, sources: SourceClient
) -> Application:
    application = get_visible(session, user, application_id)
    current = ApplicationStatus(application.status)
    # Повторная отправка после запроса документов — отдельная операция resubmit.
    # Повторный submit получает 409 и не запускает обработку второй раз.
    if current != ApplicationStatus.DRAFT:
        raise InvalidTransitionError(current, ApplicationStatus.SUBMITTED)
    _validate_for_submit(application)

    change_status(session, application, ApplicationStatus.SUBMITTED, user)
    application.submitted_at = application.status_changed_at
    process_submitted(session, application, sources)
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise ApiError(
            409, ErrorCode.VERSION_CONFLICT, "Заявку уже изменили, обновите страницу"
        ) from exc
    return application


def history(session: Session, user: User, application_id: UUID) -> list[StatusHistoryEntry]:
    application = get_visible(session, user, application_id)
    query = (
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == application.id)
        .order_by(ApplicationStatusHistory.created_at, ApplicationStatusHistory.id)
    )
    return [
        StatusHistoryEntry(
            from_status=row.from_status,
            to_status=row.to_status,
            actor_type=row.actor_type,
            created_at=row.created_at,
        )
        for row in session.scalars(query)
    ]


def _latest[T](
    session: Session, model: type[T], application: Application, *where: object
) -> T | None:
    query = (
        select(model)
        .where(model.application_id == application.id, *where)  # type: ignore[attr-defined]
        .order_by(model.created_at.desc())  # type: ignore[attr-defined]
        .limit(1)
    )
    return session.scalar(query)


def _client_decision(row: DecisionRow | None) -> ClientDecision | None:
    """Клиенту — только итог, кто решил и код отказа. Баллы и трасса правил остаются в БД."""
    if row is None:
        return None
    outcome = DecisionOutcome(row.outcome.lower())
    return ClientDecision(
        outcome=outcome,
        decided_by=row.decided_by,
        reason_code=row.client_reason if outcome == DecisionOutcome.REJECTED else None,
        decided_at=row.created_at,
    )


def _client_offer(row: OfferRow | None) -> Offer | None:
    if row is None:
        return None
    return Offer(
        id=row.id,
        product_id=row.product_id,
        amount=row.amount,
        term_months=row.term_months,
        rate=row.rate,
        monthly_payment=row.monthly_payment,
        status=row.status,
    )


def _open_info_request(session: Session, application: Application) -> InfoRequest | None:
    row = _latest(session, InfoRequestRow, application, InfoRequestRow.status == "open")
    if row is None:
        return None
    return InfoRequest(
        id=row.id,
        status=row.status,
        items=[InfoRequestItem.model_validate(item) for item in row.items],
        message=row.message,
        created_at=row.created_at,
    )


def to_detail(session: Session, application: Application) -> ApplicationDetail:
    return ApplicationDetail(
        id=application.id,
        number=application.number,
        company_id=application.company_id,
        applicant_id=application.applicant_id,
        product_id=application.product_id,
        amount=application.amount,
        term_months=application.term_months,
        purpose=application.purpose,
        revenue_12m=application.revenue_12m,
        existing_payments_monthly=application.existing_payments_monthly,
        bki_consent=application.bki_consent,
        status=application.status,
        status_changed_at=application.status_changed_at,
        version=application.version,
        submitted_at=application.submitted_at,
        # Последний оффер не обнуляется после принятия (описание поля в контракте).
        active_offer=_client_offer(_latest(session, OfferRow, application)),
        decision=_client_decision(_latest(session, DecisionRow, application)),
        info_request=_open_info_request(session, application),
        documents=[],  # загрузка документов — следующий этап
    )


def to_summary(session: Session, application: Application) -> ApplicationSummary:
    return ApplicationSummary(
        id=application.id,
        number=application.number,
        status=application.status,
        status_changed_at=application.status_changed_at,
        product_id=application.product_id,
        amount=application.amount,
        term_months=application.term_months,
        submitted_at=application.submitted_at,
        info_request=_open_info_request(session, application),
    )

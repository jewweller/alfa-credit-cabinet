"""Кабинет банка: очередь, карточка андеррайтера, «взять в работу», решение (экраны B2–B4).

Сотрудник видит заявки всех клиентов, кроме черновиков. Решение принимается только в
MANUAL_REVIEW: одобрение, другие условия, запрос документов или отказ — те же следствия, что
у движка (оффер, запрос документов), но `decided_by = underwriter`.

Временные правила backend (U1–U5, docs/analyst-questions.md, раздел 8) — аналитиком не
подтверждены:
  * решить можно и без «взять в работу»: заявка закрепляется за тем, кто решил (как в моках);
  * комментарий обязателен только для запроса документов — как в контракте и форме B4;
    `manual_decision.comment_required` и `load_over_limit` из config.yaml не применяются;
  * одобрение — на сумму и срок из заявки, другие условия — в лимитах выбранного продукта.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.errors import ApiError
from app.db.models import (
    Application,
    DecisionRow,
    EnrichmentResult,
    InfoRequestRow,
    OfferRow,
    Product,
    ScoringResultRow,
    User,
)
from app.domain.state_machine import ApplicationStatus
from app.schemas.bank import (
    BankApplicationDetail,
    BankApplicationSummary,
    BankDecision,
    Employee,
    EnrichmentSource,
    EnrichmentStatus,
    Grade,
    RuleCheck,
    ScoringFactor,
    ScoringResult,
    UnderwriterDecisionRequest,
    UnderwriterOutcome,
)
from app.schemas.bank import EnrichmentResult as EnrichmentInfo
from app.schemas.common import ErrorCode
from app.schemas.companies import CompanyBrief, CompanyLookupResponse
from app.schemas.decisions import DecisionActor, DecisionOutcome
from app.scoring.config import EngineConfig, load_config
from app.scoring.finance import monthly_payment
from app.services.applications import _latest, to_detail
from app.services.companies import _from_egrip, _from_egrul
from app.services.status import change_status

# Названия правил — как в таблице плана (раздел 7) и в моках фронта.
RULE_TITLES = {
    "R1": "Компания не действующая в ЕГРЮЛ/ЕГРИП",
    "R2": "Банкротство или текущая просрочка больше 90 дней (БКИ)",
    "R3": "Источник не ответил после 2 повторов",
    "R4": "Выручка в анкете расходится с ФНС больше чем на 30%",
    "R5": "Сумма больше 10 млн ₽",
    "R6": "Грейд E",
    "R7": "Грейд D",
    "R8": "Грейд C",
    "R9": "Грейд A/B и нагрузка не выше 35%",
    "R10": "Грейд A/B и нагрузка выше 35%",
}

_ENRICHMENT_STATUS = {"ok": EnrichmentStatus.OK, "not_found": EnrichmentStatus.NOT_FOUND}
_REGISTRY = {"egrul": _from_egrul, "egrip": _from_egrip}


# ── Чтение ────────────────────────────────────────────────────────────────────


def _employee(user: User | None) -> Employee | None:
    return Employee(id=user.id, full_name=user.full_name) if user else None


def _company(application: Application) -> CompanyBrief:
    company = application.company
    return CompanyBrief(
        id=company.id,
        inn=company.inn,
        name=company.name,
        kind=company.kind,
        okved_main=company.okved_main,
        segment=company.segment,
    )


def _not_found() -> ApiError:
    return ApiError(404, ErrorCode.NOT_FOUND, "Заявка не найдена")


def _get(session: Session, application_id: UUID) -> Application:
    application = session.get(Application, application_id)
    if application is None or application.status == ApplicationStatus.DRAFT:
        raise _not_found()
    return application


def list_queue(
    session: Session,
    statuses: list[ApplicationStatus] | None,
    grade: Grade | None,
    product_id: UUID | None,
) -> list[BankApplicationSummary]:
    query = select(Application).where(Application.status != ApplicationStatus.DRAFT)
    if statuses:
        query = query.where(Application.status.in_([str(s) for s in statuses]))
    if product_id is not None:
        query = query.where(Application.product_id == product_id)
    rows = []
    for application in session.scalars(query):
        scoring = _latest(session, ScoringResultRow, application)
        if grade is not None and (scoring is None or scoring.grade != grade):
            continue
        rows.append(
            BankApplicationSummary(
                id=application.id,
                number=application.number,
                company=_company(application),
                product_id=application.product_id,
                amount=application.amount,
                term_months=application.term_months,
                status=application.status,
                status_changed_at=application.status_changed_at,
                submitted_at=application.submitted_at,
                score=scoring.total_score if scoring else None,
                grade=scoring.grade if scoring else None,
                assignee=_employee(application.assignee),
            )
        )
    # Сначала MANUAL_REVIEW, дольше всего ждущие — выше; затем остальные, свежие сверху.
    waiting = sorted(
        (r for r in rows if r.status == ApplicationStatus.MANUAL_REVIEW),
        key=lambda r: r.status_changed_at,
    )
    rest = sorted(
        (r for r in rows if r.status != ApplicationStatus.MANUAL_REVIEW),
        key=lambda r: r.status_changed_at,
        reverse=True,
    )
    return waiting + rest


def _enrichment(session: Session, application: Application) -> list[EnrichmentResult]:
    """Последний ответ каждого источника (после resubmit обогащение проходит заново)."""
    query = (
        select(EnrichmentResult)
        .where(EnrichmentResult.application_id == application.id)
        .order_by(EnrichmentResult.fetched_at)
    )
    latest = {row.source: row for row in session.scalars(query)}
    return list(latest.values())


def _registry(rows: list[EnrichmentResult]) -> CompanyLookupResponse | None:
    for row in rows:
        if row.source in _REGISTRY and row.status == "ok" and row.response:
            return _REGISTRY[row.source](row.response)
    return None


def _number(value: str) -> str:
    return f"{Decimal(value).normalize():f}".replace(".", ",")


def _plural_years(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "год"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "года"
    return "лет"


def _factor_value(unit: str, value: str | None, note: str | None) -> str:
    if value is None:
        return note or "нет данных"
    if unit == "full_years":
        years = int(Decimal(value))
        return f"{years} {_plural_years(years)}"
    if unit == "days":
        return "без просрочек" if Decimal(value) == 0 else f"{_number(value)} дн."
    if unit == "percent":
        return f"{_number(str(Decimal(value).quantize(Decimal('0.1'))))}%"
    if unit == "rub":
        return "нет" if Decimal(value) == 0 else f"{Decimal(value):,.0f} ₽".replace(",", " ")
    return _number(value)  # flags — число признаков


def _scoring(row: ScoringResultRow | None, config: EngineConfig) -> ScoringResult | None:
    if row is None:
        return None
    data: dict[str, Any] = row.factors
    debt_load = data.get("debt_load_pct")
    factors = config.scoring.factors
    return ScoringResult(
        model_version=row.model_version,
        total_score=row.total_score,
        grade=row.grade,
        debt_load=float(Decimal(debt_load) / 100) if debt_load is not None else 0.0,
        factors=[
            ScoringFactor(
                code=f["id"],
                title=factors[f["id"]].name if f["id"] in factors else f["name"],
                value=_factor_value(
                    factors[f["id"]].unit if f["id"] in factors else "flags",
                    f["value"],
                    f.get("note"),
                ),
                points=f["points"],
                max_points=f["max_points"],
            )
            for f in data["factors"]
        ],
    )


def _rules(session: Session, application: Application) -> list[RuleCheck]:
    """Трасса R1–R10 последнего решения движка (решение специалиста её не заменяет)."""
    row = _latest(session, DecisionRow, application, DecisionRow.decided_by == "system")
    if row is None:
        return []
    return [
        RuleCheck(
            code=check["rule"],
            title=RULE_TITLES.get(check["rule"], check["rule"]),
            fired=check["fired"],
            detail=check.get("detail"),
        )
        for check in row.rules_fired.get("checks", [])
    ]


def _decision(session: Session, application: Application) -> BankDecision | None:
    row = _latest(session, DecisionRow, application)
    if row is None:
        return None
    underwriter = session.get(User, row.underwriter_id) if row.underwriter_id else None
    return BankDecision(
        outcome=row.outcome.lower(),
        decided_by=row.decided_by,
        reason_code=row.client_reason if row.outcome.lower() == DecisionOutcome.REJECTED else None,
        decided_at=row.created_at,
        underwriter=_employee(underwriter),
        comment=row.comment,
    )


def to_bank_detail(
    session: Session, application: Application, config: EngineConfig | None = None
) -> BankApplicationDetail:
    config = config or load_config()
    enrichment = _enrichment(session, application)
    applicant = session.get(User, application.applicant_id)
    return BankApplicationDetail(
        application=to_detail(session, application),
        company=_company(application),
        applicant_name=applicant.full_name if applicant else "—",
        registry=_registry(enrichment),
        assignee=_employee(application.assignee),
        enrichment=[
            EnrichmentInfo(
                source=EnrichmentSource(row.source),
                status=_ENRICHMENT_STATUS.get(row.status, EnrichmentStatus.ERROR),
                attempts=row.attempts,
                fetched_at=row.fetched_at,
                response=row.response if row.status == "ok" else None,
            )
            for row in enrichment
        ],
        scoring=_scoring(_latest(session, ScoringResultRow, application), config),
        rules=_rules(session, application),
        decision=_decision(session, application),
    )


def detail(session: Session, application_id: UUID) -> BankApplicationDetail:
    return to_bank_detail(session, _get(session, application_id))


# ── Действия ──────────────────────────────────────────────────────────────────


def _in_review(application: Application, message: str) -> None:
    if application.status != ApplicationStatus.MANUAL_REVIEW:
        raise ApiError(409, ErrorCode.INVALID_TRANSITION, message)


def _not_taken_by_other(application: Application, user: User) -> None:
    if application.assignee_id is not None and application.assignee_id != user.id:
        name = application.assignee.full_name if application.assignee else "другой специалист"
        raise ApiError(409, ErrorCode.ASSIGNED_TO_OTHER, f"Заявку уже ведёт {name}")


def _commit(session: Session) -> None:
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise ApiError(
            409, ErrorCode.VERSION_CONFLICT, "Заявку уже изменили, обновите страницу"
        ) from exc


def assign(session: Session, user: User, application_id: UUID) -> BankApplicationDetail:
    application = _get(session, application_id)
    _in_review(application, "Взять в работу можно только заявку на ручном рассмотрении")
    _not_taken_by_other(application, user)
    if application.assignee_id != user.id:
        application.assignee_id = user.id
        _commit(session)
        session.refresh(application)
    return to_bank_detail(session, application)


def _invalid(field: str, message: str) -> ApiError:
    return ApiError(422, ErrorCode.VALIDATION_ERROR, message, field)


def _offer_terms(
    session: Session, application: Application, body: UnderwriterDecisionRequest
) -> tuple[Product, Decimal, int]:
    if body.outcome == UnderwriterOutcome.APPROVED:
        assert application.product is not None  # заявка прошла submit
        return application.product, application.amount, application.term_months  # type: ignore[return-value]
    product = session.get(Product, body.product_id)
    if product is None:
        raise _invalid("product_id", "Продукт не найден")
    assert body.amount is not None and body.term_months is not None  # проверено схемой
    if not product.min_amount <= body.amount <= product.max_amount:
        raise _invalid(
            "amount",
            f"Сумма для «{product.name}» — от {product.min_amount} до {product.max_amount} ₽",
        )
    if not product.min_term <= body.term_months <= product.max_term:
        raise _invalid(
            "term_months",
            f"Срок для «{product.name}» — от {product.min_term} до {product.max_term} мес",
        )
    return product, body.amount, body.term_months


def decide(
    session: Session,
    user: User,
    application_id: UUID,
    body: UnderwriterDecisionRequest,
    config: EngineConfig | None = None,
) -> BankApplicationDetail:
    config = config or load_config()
    application = _get(session, application_id)
    _in_review(application, "Решение принимается только на ручном рассмотрении")
    _not_taken_by_other(application, user)

    note = (body.comment or "").strip() or None
    decision = DecisionRow(
        application_id=application.id,
        outcome=str(body.outcome).upper(),
        reason_code=f"MANUAL_{str(body.outcome).upper()}",
        client_reason=body.reason_code if body.outcome == UnderwriterOutcome.REJECTED else None,
        rules_fired={"config_version": config.config_version, "rule": None, "checks": []},
        decided_by=DecisionActor.UNDERWRITER,
        underwriter_id=user.id,
        # Для запроса документов текст — сообщение клиенту, а не внутренний комментарий.
        comment=None if body.outcome == UnderwriterOutcome.INFO_REQUESTED else note,
    )
    if body.outcome in (UnderwriterOutcome.APPROVED, UnderwriterOutcome.COUNTER_OFFER):
        assert body.rate  # схема требует ставку больше нуля
        product, amount, term = _offer_terms(session, application, body)
        session.add(decision)
        session.flush()
        session.add(
            OfferRow(
                application_id=application.id,
                decision_id=decision.id,
                product_id=product.id,
                amount=amount,
                term_months=term,
                rate=body.rate,
                monthly_payment=monthly_payment(config, amount, body.rate, term),
                status="active",
            )
        )
    elif body.outcome == UnderwriterOutcome.INFO_REQUESTED:
        assert body.info_items  # проверено схемой
        session.add(decision)
        session.flush()
        session.add(
            InfoRequestRow(
                application_id=application.id,
                decision_id=decision.id,
                items=[item.model_dump(mode="json") for item in body.info_items],
                message=note,
                status="open",
            )
        )
    else:
        session.add(decision)

    application.assignee_id = user.id
    change_status(session, application, ApplicationStatus(str(body.outcome).upper()), user)
    _commit(session)
    session.refresh(application)
    return to_bank_detail(session, application, config)

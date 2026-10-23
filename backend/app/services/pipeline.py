"""Обработка отправленной заявки: обогащение → скоринг → решение (план, раздел 4, этапы 3–5).

Пока выполняется синхронно внутри submit, в той же транзакции: либо сохраняется всё
(статусы, история, ответы источников, скоринг, решение, оффер / запрос документов),
либо ничего. Отдельного воркера и пауз между шагами нет — это следующий этап.

Сбой источника — не ошибка: его обрабатывают правила (R1 — «не найдено», R3 — «недоступен»).
Сбой движка (исключение при разборе ответов, скоринге или решении) — не бизнес-отказ:
решение SYS_ENGINE_ERROR и MANUAL_REVIEW (config.yaml, pipeline.on_step_failure_reason_code).
"""

import logging
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    DecisionRow,
    EnrichmentResult,
    InfoRequestRow,
    OfferRow,
    Product,
    ScoringResultRow,
)
from app.decision.engine import Decision, decide
from app.domain.state_machine import ApplicationStatus
from app.integrations.base import FetchResult, SourceClient
from app.integrations.parsing import to_applicant_sources
from app.scoring.config import EngineConfig, load_config
from app.scoring.engine import ScoringResult, score
from app.scoring.inputs import LoanRequest, ProductTerms
from app.services.status import change_status

log = logging.getLogger(__name__)


def _terms(product: Product) -> ProductTerms:
    return ProductTerms(
        id=product.id,
        code=product.code,
        name=product.name,
        purposes=tuple(product.purpose_tags),
        min_amount=product.min_amount,
        max_amount=product.max_amount,
        min_term=product.min_term,
        max_term=product.max_term,
        base_rate=product.base_rate,
    )


def _loan_request(application: Application) -> LoanRequest:
    assert application.product is not None  # submit уже проверил полноту
    return LoanRequest(
        product=_terms(application.product),
        amount=application.amount,
        term_months=application.term_months,
        purpose=application.purpose,
        revenue_12m=application.revenue_12m,
        existing_payments_monthly=application.existing_payments_monthly,
    )  # type: ignore[arg-type]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


def _fetch_all(
    session: Session, application: Application, sources: SourceClient, config: EngineConfig
) -> dict[str, FetchResult]:
    company = application.company
    results: dict[str, FetchResult] = {}
    for source in config.integrations.required_sources[company.kind]:
        result = sources.fetch(source, company.inn)
        results[source] = result
        session.add(
            EnrichmentResult(
                application_id=application.id,
                source=source,
                status=result.state,
                response=result.payload,
                attempts=result.attempts,
                error=result.error,
            )
        )
    return results


def _save_result(
    session: Session, application: Application, scoring: ScoringResult, decision: Decision
) -> None:
    scoring_row = ScoringResultRow(
        application_id=application.id,
        model_version=scoring.config_version,
        total_score=scoring.total,
        grade=scoring.grade,
        factors=_jsonable(
            {
                "reference_date": scoring.reference_date.isoformat(),
                "new_payment_base_rate": scoring.new_payment_base_rate,
                "debt_load_pct": scoring.debt_load_pct,
                "factors": [asdict(f) for f in scoring.factors],
            }
        ),
    )
    session.add(scoring_row)
    session.flush()
    decision_row = DecisionRow(
        application_id=application.id,
        scoring_result_id=scoring_row.id,
        outcome=decision.outcome,
        reason_code=decision.reason_code,
        client_reason=decision.client_reason,
        rules_fired={
            "config_version": decision.config_version,
            "rule": decision.rule,
            "staff_message": decision.staff_message,
            "checks": [asdict(c) for c in decision.checks],
        },
        decided_by="system",
    )
    session.add(decision_row)
    session.flush()
    if decision.offer is not None:
        offer = decision.offer
        session.add(
            OfferRow(
                application_id=application.id,
                decision_id=decision_row.id,
                product_id=offer.product.id,
                amount=offer.amount,
                term_months=offer.term_months,
                rate=offer.rate,
                monthly_payment=offer.monthly_payment,
                status="active",
            )
        )
    if decision.info_request_items:
        session.add(
            InfoRequestRow(
                application_id=application.id,
                decision_id=decision_row.id,
                items=[item.model_dump(mode="json") for item in decision.info_request_items],
                message=decision.client_message,
                status="open",
            )
        )


def _save_engine_failure(
    session: Session, application: Application, config: EngineConfig, error: Exception
) -> ApplicationStatus:
    code = config.pipeline.on_step_failure_reason_code
    reason = config.reason_codes[code]
    session.add(
        DecisionRow(
            application_id=application.id,
            outcome=config.outcome_of(code),
            reason_code=code,
            client_reason=reason.client_reason,
            rules_fired={
                "config_version": config.config_version,
                "rule": reason.rule,
                "staff_message": reason.staff_message.format(source=type(error).__name__),
                "error": f"{type(error).__name__}: {error}"[:500],
                "checks": [],
            },
            decided_by="system",
        )
    )
    return ApplicationStatus(config.outcome_of(code))


def process_submitted(
    session: Session,
    application: Application,
    sources: SourceClient,
    config: EngineConfig | None = None,
) -> None:
    """SUBMITTED → ENRICHMENT → SCORING → исход. Коммит — на вызывающей стороне."""
    config = config or load_config()
    change_status(session, application, ApplicationStatus.ENRICHMENT, actor=None)
    results = _fetch_all(session, application, sources, config)
    change_status(session, application, ApplicationStatus.SCORING, actor=None)

    try:
        request = _loan_request(application)
        applicant = to_applicant_sources(application.company.kind, results)
        scoring = score(request, applicant, config)
        products = [_terms(p) for p in session.scalars(select(Product).order_by(Product.code))]
        decision = decide(request, applicant, scoring, products, False, config)
    except Exception as error:  # noqa: BLE001 — любой сбой движка уходит специалисту
        log.exception("сбой обработки заявки %s", application.id)
        target = _save_engine_failure(session, application, config, error)
    else:
        _save_result(session, application, scoring, decision)
        target = ApplicationStatus(decision.outcome)
    change_status(session, application, target, actor=None)

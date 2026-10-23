"""Сквозной путь через API: submit → обогащение → скоринг → решение → GET заявки.

Данные источников — mocks/fixtures (черновик, см. README там), анкеты — docs/plan.md, раздел 7.
"""

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from conftest import auth_headers
from demo_flows import BAKERY, EXPRESS_WC, KOVALEV, MELNIKOVA, STROY
from demo_flows import PIPELINE_STEPS as _PIPELINE
from demo_flows import rows as _rows
from demo_flows import steps as _steps
from demo_flows import submit_demo as _submit
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    DecisionRow,
    EnrichmentResult,
    InfoRequestRow,
    OfferRow,
    ScoringResultRow,
)
from app.integrations.base import FetchResult
from app.integrations.fixtures import get_source_client
from app.scoring.inputs import SourceState

_INTERNAL_MARKERS = (
    "total_score",
    "grade",
    "factors",
    "rules_fired",
    "checks",
    "R9_",
    "R10_",
    "F1",
)


def _assert_no_internal_data(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for marker in _INTERNAL_MARKERS:
        assert marker not in text, f"клиенту ушло внутреннее поле: {marker}"


# ── Четыре исхода ────────────────────────────────────────────────────────────


def test_bakery_is_approved(client: TestClient, engine: Engine) -> None:
    app, headers = _submit(client, *BAKERY)

    assert app["status"] == "APPROVED"
    assert app["decision"]["outcome"] == "approved"
    assert app["decision"]["decided_by"] == "system"
    assert app["decision"]["reason_code"] is None
    offer = app["active_offer"]
    assert (offer["product_id"], offer["amount"], offer["term_months"]) == (
        EXPRESS_WC, "3000000.00", 12,
    )  # fmt: skip
    assert (offer["rate"], offer["monthly_payment"], offer["status"]) == (
        "18.00",
        "275040.00",
        "active",
    )  # fmt: skip — платёж до рубля по config.yaml (вопрос K1)
    assert app["info_request"] is None
    assert _steps(client, app, headers) == [*_PIPELINE, ("SCORING", "APPROVED", "system")]
    _assert_no_internal_data(app)

    [scoring] = _rows(engine, ScoringResultRow, app["id"])
    [decision] = _rows(engine, DecisionRow, app["id"])
    assert (scoring.total_score, scoring.grade, scoring.model_version) == (100, "A", "1.0.0")
    assert decision.reason_code == "R9_APPROVED"
    assert decision.rules_fired["config_version"] == "1.0.0"
    assert [c["rule"] for c in decision.rules_fired["checks"]][-1] == "R9"
    assert decision.scoring_result_id == scoring.id
    sources = {r.source: r.status for r in _rows(engine, EnrichmentResult, app["id"])}
    assert sources == {"egrul": "ok", "fns_tb": "ok", "bki": "ok"}


def test_kovalev_gets_counter_offer(client: TestClient, engine: Engine) -> None:
    app, headers = _submit(client, *KOVALEV)

    assert app["status"] == "COUNTER_OFFER"
    assert app["decision"]["outcome"] == "counter_offer"
    offer = app["active_offer"]
    # План, раздел 7: просили 2 млн / 12 мес, предлагаем 2 млн / 24 мес под 20 %.
    assert (offer["amount"], offer["term_months"], offer["rate"]) == ("2000000.00", 24, "20.00")
    assert offer["monthly_payment"] == "101792.00"
    assert _steps(client, app, headers)[-1] == ("SCORING", "COUNTER_OFFER", "system")
    [decision] = _rows(engine, DecisionRow, app["id"])
    assert decision.reason_code == "R10_COUNTER_OFFER"
    sources = {r.source for r in _rows(engine, EnrichmentResult, app["id"])}
    assert sources == {"egrip", "fns_tb", "bki"}  # ИП — реестр ЕГРИП


def test_stroyresurs_is_rejected_but_scored(client: TestClient, engine: Engine) -> None:
    app, headers = _submit(client, *STROY)

    assert app["status"] == "REJECTED"
    assert app["decision"] == {
        "outcome": "rejected",
        "decided_by": "system",
        "reason_code": "company_inactive",
        "decided_at": app["decision"]["decided_at"],
    }
    assert app["active_offer"] is None and app["info_request"] is None
    assert _steps(client, app, headers)[-1] == ("SCORING", "REJECTED", "system")
    [decision] = _rows(engine, DecisionRow, app["id"])
    assert decision.reason_code == "R1_LIQUIDATED"
    # Скоринг посчитан и сохранён, хотя решение — отказ (план, раздел 4).
    assert len(_rows(engine, ScoringResultRow, app["id"])) == 1
    # ФНС и БКИ для СтройРесурса в фикстурах нет (D7): «недоступны», но R1 срабатывает раньше R3.
    sources = {r.source: r.status for r in _rows(engine, EnrichmentResult, app["id"])}
    assert sources == {"egrul": "ok", "fns_tb": "unavailable", "bki": "unavailable"}


def test_melnikova_is_asked_for_documents(client: TestClient, engine: Engine) -> None:
    app, headers = _submit(client, *MELNIKOVA)

    assert app["status"] == "INFO_REQUESTED"
    assert app["decision"]["outcome"] == "info_requested"
    assert app["active_offer"] is None
    request = app["info_request"]
    assert request["status"] == "open"
    assert request["items"] == [
        {"kind": "tax_return", "title": "Декларация или выписка за прошлый год", "required": True}
    ]
    assert "ФНС" in request["message"]
    listed = client.get("/api/v1/applications", headers=headers).json()
    assert listed[0]["info_request"]["id"] == request["id"]
    [decision] = _rows(engine, DecisionRow, app["id"])
    assert decision.reason_code == "R4_REVENUE_PROOF_REQUIRED"
    assert len(_rows(engine, InfoRequestRow, app["id"])) == 1


# ── Повторы, доступ, сбои ───────────────────────────────────────────────────


def test_second_submit_is_conflict_and_creates_nothing(client: TestClient, engine: Engine) -> None:
    app, headers = _submit(client, *BAKERY)

    again = client.post(f"/api/v1/applications/{app['id']}/submit", headers=headers)

    assert again.status_code == 409
    assert again.json()["code"] == "invalid_transition"
    for model in (DecisionRow, OfferRow, ScoringResultRow):
        assert len(_rows(engine, model, app["id"])) == 1
    assert len(_rows(engine, EnrichmentResult, app["id"])) == 3


def test_other_company_cannot_see_result(client: TestClient) -> None:
    app, _ = _submit(client, *BAKERY)
    kovalev = auth_headers(client, "kovalev@demo.local")

    assert client.get(f"/api/v1/applications/{app['id']}", headers=kovalev).status_code == 404
    assert (
        client.post(f"/api/v1/applications/{app['id']}/submit", headers=kovalev).status_code == 404
    )


def test_engine_failure_goes_to_manual_review_not_rejection(
    client: TestClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_score(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("scoring exploded")

    monkeypatch.setattr("app.services.pipeline.score", broken_score)

    app, headers = _submit(client, *BAKERY)

    assert app["status"] == "MANUAL_REVIEW"
    assert app["decision"]["outcome"] == "manual_review"
    assert app["decision"]["reason_code"] is None
    assert app["active_offer"] is None
    assert _steps(client, app, headers)[-1] == ("SCORING", "MANUAL_REVIEW", "system")
    [decision] = _rows(engine, DecisionRow, app["id"])
    assert decision.reason_code == "SYS_ENGINE_ERROR"
    assert decision.scoring_result_id is None
    assert "RuntimeError" in decision.rules_fired["error"]
    assert _rows(engine, ScoringResultRow, app["id"]) == []


class _BkiDown:
    """Источник, у которого БКИ не ответило после повторов."""

    def __init__(self) -> None:
        self._real = get_source_client()

    def fetch(self, source: str, inn: str) -> FetchResult:
        if source == "bki":
            return FetchResult(source, SourceState.UNAVAILABLE, attempts=3, error="HTTP 503")
        return self._real.fetch(source, inn)


def test_unavailable_source_is_handled_by_r3(client: TestClient, engine: Engine) -> None:
    client.app.dependency_overrides[get_source_client] = _BkiDown  # type: ignore[attr-defined]

    app, _ = _submit(client, *BAKERY)

    assert app["status"] == "MANUAL_REVIEW"
    [decision] = _rows(engine, DecisionRow, app["id"])
    assert decision.reason_code == "R3_SOURCE_UNAVAILABLE"
    [bki] = [r for r in _rows(engine, EnrichmentResult, app["id"]) if r.source == "bki"]
    assert (bki.status, bki.attempts, bki.error) == ("unavailable", 3, "HTTP 503")


def test_processing_is_atomic_with_submit(
    client: TestClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Сбой записи результата (не движка) откатывает и отправку: заявка остаётся черновиком.
    def broken_save(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.services.pipeline._save_result", broken_save)
    headers = auth_headers(client, BAKERY[0])
    created = client.post("/api/v1/applications", json={}, headers=headers).json()
    client.patch(
        f"/api/v1/applications/{created['id']}",
        json={"version": created["version"], **BAKERY[1]},
        headers=headers,
    )

    with pytest.raises(OSError):
        client.post(f"/api/v1/applications/{created['id']}/submit", headers=headers)

    with Session(engine) as session:
        assert session.get(Application, UUID(created["id"])).status == "DRAFT"
        assert session.scalar(select(func.count()).select_from(EnrichmentResult)) == 0


def test_money_values_are_exact_decimals(engine: Engine, client: TestClient) -> None:
    app, _ = _submit(client, *KOVALEV)

    [offer] = _rows(engine, OfferRow, app["id"])
    assert offer.monthly_payment == Decimal("101792.00")

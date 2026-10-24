"""Кабинет банка: очередь, карточка, «взять в работу», решение специалиста, доступ."""

from pathlib import Path

import pytest
from conftest import DEMO_PASSWORD, auth_headers
from demo_flows import BAKERY, EXPRESS_WC, MIRAGE, SBOY, create_draft, steps, submit_demo
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.models import User
from app.security import hash_password
from app.storage import LocalStorage, get_storage

UNDERWRITER = "underwriter@demo.local"
ADMIN = "admin@demo.local"
EQUIPMENT = "7f1c2b0a-0000-4000-8000-000000000002"
PDF = b"%PDF-1.7\n% demo declaration\n"


def _bank(client: TestClient, email: str = UNDERWRITER) -> dict:
    return auth_headers(client, email)


def _queue(client: TestClient, headers: dict, **params):  # noqa: ANN003, ANN202
    return client.get("/api/v1/bank/applications", params=params, headers=headers)


def _card(client: TestClient, app_id: str, headers: dict):  # noqa: ANN202
    return client.get(f"/api/v1/bank/applications/{app_id}", headers=headers)


def _assign(client: TestClient, app_id: str, headers: dict):  # noqa: ANN202
    return client.post(f"/api/v1/bank/applications/{app_id}/assign", headers=headers)


def _decide(client: TestClient, app_id: str, headers: dict, body: dict):  # noqa: ANN202
    return client.post(
        f"/api/v1/bank/applications/{app_id}/decision",
        json=body,
        headers={**headers, "Idempotency-Key": "decide-1"},
    )


def _client_view(client: TestClient, app: dict, headers: dict) -> dict:
    return client.get(f"/api/v1/applications/{app['id']}", headers=headers).json()


# ── Очередь (B2) ────────────────────────────────────────────────────────────


def test_queue_puts_manual_review_first_oldest_on_top(client: TestClient) -> None:
    mirage, _ = submit_demo(client, *MIRAGE)
    bakery, _ = submit_demo(client, *BAKERY)
    sboy, _ = submit_demo(client, *SBOY)
    create_draft(client, *BAKERY)  # черновик банку не виден

    rows = _queue(client, _bank(client)).json()

    assert [r["id"] for r in rows] == [mirage["id"], sboy["id"], bakery["id"]]
    assert [r["status"] for r in rows] == ["MANUAL_REVIEW", "MANUAL_REVIEW", "APPROVED"]
    first = rows[0]
    assert (first["score"], first["grade"], first["assignee"]) == (40, "D", None)
    assert first["company"]["inn"] and first["number"]


def test_queue_filters_by_status_grade_and_product(client: TestClient) -> None:
    mirage, _ = submit_demo(client, *MIRAGE)
    bakery, _ = submit_demo(client, *BAKERY)
    headers = _bank(client)

    by_status = _queue(client, headers, status=["APPROVED", "REJECTED"]).json()
    by_grade = _queue(client, headers, grade="D").json()
    by_product = _queue(client, headers, product_id=EQUIPMENT).json()

    assert [r["id"] for r in by_status] == [bakery["id"]]
    assert [r["id"] for r in by_grade] == [mirage["id"]]
    assert by_product == []


def test_admin_sees_queue_client_does_not(client: TestClient) -> None:
    submit_demo(client, *MIRAGE)

    assert len(_queue(client, _bank(client, ADMIN)).json()) == 1
    assert _queue(client, auth_headers(client, "bakery@demo.local")).status_code == 403
    assert client.get("/api/v1/bank/applications").status_code == 401


# ── Карточка (B3) ───────────────────────────────────────────────────────────


def test_card_shows_sources_scoring_rules_and_engine_decision(client: TestClient) -> None:
    app, _ = submit_demo(client, *MIRAGE)

    card = _card(client, app["id"], _bank(client)).json()

    assert card["application"]["id"] == app["id"]
    assert card["applicant_name"] == "Анна Зайцева"
    assert card["registry"]["inn"] == card["company"]["inn"]
    assert {e["source"]: e["status"] for e in card["enrichment"]} == {
        "egrul": "ok",
        "fns_tb": "ok",
        "bki": "ok",
    }
    scoring = card["scoring"]
    assert (scoring["total_score"], scoring["grade"]) == (40, "D")
    assert [f["code"] for f in scoring["factors"]] == ["F1", "F2", "F3", "F4", "F5", "F6"]
    assert sum(f["points"] for f in scoring["factors"]) == 40
    assert all(f["value"] for f in scoring["factors"])
    assert card["rules"][-1]["code"] == "R7" and card["rules"][-1]["fired"] is True
    assert not any(r["fired"] for r in card["rules"][:-1])
    assert card["decision"]["outcome"] == "manual_review"
    assert card["decision"]["decided_by"] == "system"
    assert card["decision"]["underwriter"] is None


def test_card_shows_failed_bki_without_response(client: TestClient) -> None:
    app, _ = submit_demo(client, *SBOY)

    card = _card(client, app["id"], _bank(client)).json()

    [bki] = [e for e in card["enrichment"] if e["source"] == "bki"]
    assert (bki["status"], bki["attempts"], bki["response"]) == ("error", 3, None)
    assert card["rules"][-1]["code"] == "R3"


def test_draft_and_unknown_cards_are_404(client: TestClient) -> None:
    draft, _ = create_draft(client, *BAKERY)
    headers = _bank(client)

    assert _card(client, draft["id"], headers).status_code == 404
    assert _card(client, "00000000-0000-4000-8000-000000000000", headers).status_code == 404


# ── Взять в работу ──────────────────────────────────────────────────────────


def test_assign_is_idempotent_for_same_employee(client: TestClient) -> None:
    app, _ = submit_demo(client, *MIRAGE)
    headers = _bank(client)

    first = _assign(client, app["id"], headers)
    again = _assign(client, app["id"], headers)

    assert first.status_code == again.status_code == 200
    assert again.json()["assignee"]["full_name"] == "Дмитрий Орлов"
    assert _queue(client, headers).json()[0]["assignee"]["full_name"] == "Дмитрий Орлов"


def _second_underwriter(engine: Engine) -> str:
    with Session(engine) as session:
        session.add(
            User(
                email="underwriter2@demo.local",
                password_hash=hash_password(DEMO_PASSWORD),
                role="underwriter",
                full_name="Мария Лебедева",
            )
        )
        session.commit()
    return "underwriter2@demo.local"


def test_assigned_application_is_closed_to_other_employee(
    client: TestClient, engine: Engine
) -> None:
    app, _ = submit_demo(client, *MIRAGE)
    _assign(client, app["id"], _bank(client))
    other = _bank(client, _second_underwriter(engine))

    taken = _assign(client, app["id"], other)
    decided = _decide(client, app["id"], other, {"outcome": "rejected", "reason_code": "low_score"})

    assert taken.status_code == decided.status_code == 409
    assert taken.json()["code"] == decided.json()["code"] == "assigned_to_other"


def test_admin_only_views_bank_cabinet(client: TestClient) -> None:
    """Вариант D: администратор видит очередь и карточку, но не берёт в работу и не решает."""
    app, _ = submit_demo(client, *MIRAGE)
    admin = _bank(client, ADMIN)

    assert _card(client, app["id"], admin).status_code == 200
    taken = _assign(client, app["id"], admin)
    decided = _decide(client, app["id"], admin, {"outcome": "approved", "rate": "20.00"})

    assert taken.status_code == decided.status_code == 403
    assert _card(client, app["id"], admin).json()["application"]["status"] == "MANUAL_REVIEW"


def test_assign_outside_manual_review_is_invalid_transition(client: TestClient) -> None:
    app, _ = submit_demo(client, *BAKERY)

    response = _assign(client, app["id"], _bank(client))

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


# ── Решение (B4) ────────────────────────────────────────────────────────────


def test_manual_approval_then_client_signs_and_gets_money(client: TestClient) -> None:
    app, headers = submit_demo(client, *MIRAGE)
    bank = _bank(client)

    response = _decide(
        client, app["id"], bank, {"outcome": "approved", "rate": "22.00", "comment": "залог"}
    )

    assert response.status_code == 200, response.text
    card = response.json()
    assert card["application"]["status"] == "APPROVED"
    assert card["assignee"]["full_name"] == "Дмитрий Орлов"  # решивший закрепляется за заявкой
    assert card["decision"]["decided_by"] == "underwriter"
    assert card["decision"]["underwriter"]["full_name"] == "Дмитрий Орлов"
    assert card["decision"]["comment"] == "залог"
    assert card["rules"][-1]["code"] == "R7"  # трасса движка остаётся
    seen = _client_view(client, app, headers)
    offer = seen["active_offer"]
    assert (offer["amount"], offer["term_months"], offer["rate"]) == ("1500000.00", 12, "22.00")
    assert seen["decision"] == {**seen["decision"], "outcome": "approved", "reason_code": None}
    assert steps(client, app, headers)[-1] == ("MANUAL_REVIEW", "APPROVED", "underwriter")

    client.post(f"/api/v1/applications/{app['id']}/offers/{offer['id']}/accept", headers=headers)
    code = client.post(f"/api/v1/applications/{app['id']}/signing/code", headers=headers).json()
    signed = client.post(
        f"/api/v1/applications/{app['id']}/signing/confirm",
        json={"code": code["code"]},
        headers=headers,
    )
    assert signed.json()["status"] == "ISSUED"


def test_counter_offer_uses_terms_from_specialist(client: TestClient) -> None:
    app, headers = submit_demo(client, *SBOY)
    body = {
        "outcome": "counter_offer",
        "product_id": EXPRESS_WC,
        "amount": "800000.00",
        "term_months": 18,
        "rate": "21.50",
    }

    response = _decide(client, app["id"], _bank(client), body)

    assert response.json()["application"]["status"] == "COUNTER_OFFER"
    offer = _client_view(client, app, headers)["active_offer"]
    assert (offer["amount"], offer["term_months"], offer["rate"]) == ("800000.00", 18, "21.50")
    assert offer["monthly_payment"] == "52389.23"  # аннуитет 800 000 ₽, 21,5 %, 18 мес


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"amount": "6000000.00"}, "amount"),
        ({"term_months": 36}, "term_months"),
        ({"product_id": "00000000-0000-4000-8000-000000000000"}, "product_id"),
    ],
)
def test_counter_offer_outside_product_limits_is_422(
    client: TestClient, change: dict, field: str
) -> None:
    app, _ = submit_demo(client, *SBOY)
    body = {
        "outcome": "counter_offer",
        "product_id": EXPRESS_WC,
        "amount": "800000.00",
        "term_months": 18,
        "rate": "21.50",
        **change,
    }

    response = _decide(client, app["id"], _bank(client), body)

    assert response.status_code == 422
    assert response.json()["field"] == field
    card = _card(client, app["id"], _bank(client)).json()
    assert card["application"]["status"] == "MANUAL_REVIEW"  # ничего не сохранилось


def test_rejection_shows_reason_to_client(client: TestClient) -> None:
    app, headers = submit_demo(client, *MIRAGE)

    _decide(client, app["id"], _bank(client), {"outcome": "rejected", "reason_code": "low_score"})

    decision = _client_view(client, app, headers)["decision"]
    assert decision["outcome"] == "rejected"
    assert decision["decided_by"] == "underwriter"
    assert decision["reason_code"] == "low_score"
    assert "comment" not in decision  # внутренний комментарий клиенту не уходит


def test_info_request_reaches_client_and_can_be_answered(
    client: TestClient, tmp_path: Path
) -> None:
    client.app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)  # type: ignore[attr-defined]
    app, headers = submit_demo(client, *MIRAGE)
    body = {
        "outcome": "info_requested",
        "info_items": [{"kind": "bank_statement", "title": "Выписка за год", "required": True}],
        "comment": "Пришлите выписку по счёту",
    }

    card = _decide(client, app["id"], _bank(client), body).json()

    assert card["application"]["status"] == "INFO_REQUESTED"
    assert card["decision"]["comment"] is None  # текст ушёл клиенту, не во внутренний комментарий
    request = _client_view(client, app, headers)["info_request"]
    assert request["message"] == "Пришлите выписку по счёту"
    assert request["items"][0]["kind"] == "bank_statement"
    uploaded = client.post(
        f"/api/v1/applications/{app['id']}/documents",
        files={"file": ("выписка.pdf", PDF, "application/pdf")},
        data={"kind": "bank_statement", "info_request_id": request["id"]},
        headers=headers,
    )
    assert uploaded.status_code == 201
    resubmitted = client.post(f"/api/v1/applications/{app['id']}/resubmit", headers=headers)
    assert resubmitted.status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"outcome": "approved"},
        {"outcome": "approved", "rate": "0.00"},
        {"outcome": "rejected"},
        {"outcome": "info_requested", "comment": "нужны документы"},
        {
            "outcome": "info_requested",
            "info_items": [{"kind": "tax_return", "title": "Декларация", "required": True}],
        },
        {"outcome": "manual_review"},
    ],
)
def test_missing_fields_for_outcome_are_422(client: TestClient, body: dict) -> None:
    app, _ = submit_demo(client, *MIRAGE)

    response = _decide(client, app["id"], _bank(client), body)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_second_decision_is_invalid_transition(client: TestClient) -> None:
    app, _ = submit_demo(client, *MIRAGE)
    headers = _bank(client)
    _decide(client, app["id"], headers, {"outcome": "rejected", "reason_code": "low_score"})

    again = _decide(client, app["id"], headers, {"outcome": "approved", "rate": "20.00"})

    assert again.status_code == 409
    assert again.json()["code"] == "invalid_transition"


def test_decision_outside_manual_review_is_invalid_transition(client: TestClient) -> None:
    app, _ = submit_demo(client, *BAKERY)

    response = _decide(client, app["id"], _bank(client), {"outcome": "approved", "rate": "1.00"})

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


def test_client_cannot_use_bank_actions(client: TestClient) -> None:
    app, headers = submit_demo(client, *MIRAGE)

    assert _card(client, app["id"], headers).status_code == 403
    assert _assign(client, app["id"], headers).status_code == 403
    body = {"outcome": "approved", "rate": "20.00"}
    assert _decide(client, app["id"], headers, body).status_code == 403

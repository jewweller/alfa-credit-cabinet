"""Черновик → отправка → история (план, раздел 4, этапы 1–2; раздел 5)."""

from typing import Any

import pytest
from conftest import auth_headers
from fastapi.testclient import TestClient

EXPRESS_WC = "7f1c2b0a-0000-4000-8000-000000000001"
BAKERY_COMPANY = "5a0e7d6c-0000-4000-8000-0000000000cc"

# Пекарня из раздела 7 плана: 3 млн на 12 мес, выручка 24 млн, платежи 150 тыс.
BAKERY_DRAFT = {
    "product_id": EXPRESS_WC,
    "amount": "3000000.00",
    "term_months": 12,
    "purpose": "working_capital",
    "revenue_12m": "24000000.00",
    "existing_payments_monthly": "150000.00",
    "bki_consent": True,
}


def _create(client: TestClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    response = client.post("/api/v1/applications", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _patch(client: TestClient, headers: dict[str, str], app: dict[str, Any], **fields: Any) -> Any:
    return client.patch(
        f"/api/v1/applications/{app['id']}",
        json={"version": app["version"], **fields},
        headers=headers,
    )


@pytest.fixture
def bakery(client: TestClient) -> dict[str, str]:
    return auth_headers(client)


def test_create_draft(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery, product_id=EXPRESS_WC)

    assert app["status"] == "DRAFT"
    assert app["number"] == "0001"
    assert app["version"] == 1
    assert app["company_id"] == BAKERY_COMPANY
    assert app["product_id"] == EXPRESS_WC
    assert app["bki_consent"] is False
    assert app["submitted_at"] is None
    assert app["active_offer"] is None and app["decision"] is None
    assert app["info_request"] is None and app["documents"] == []


def test_numbers_increase(client: TestClient, bakery: dict[str, str]) -> None:
    assert _create(client, bakery)["number"] == "0001"
    assert _create(client, bakery)["number"] == "0002"


def test_create_rejects_unknown_product(client: TestClient, bakery: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/applications",
        json={"product_id": "00000000-0000-4000-8000-000000000000"},
        headers=bakery,
    )

    assert response.status_code == 422
    assert response.json()["field"] == "product_id"


def test_only_clients_create_applications(client: TestClient) -> None:
    headers = auth_headers(client, "underwriter@demo.local")

    response = client.post("/api/v1/applications", json={}, headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_client_sees_only_own_company(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery)
    kovalev = auth_headers(client, "kovalev@demo.local")

    assert client.get("/api/v1/applications", headers=kovalev).json() == []
    foreign = client.get(f"/api/v1/applications/{app['id']}", headers=kovalev)
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "not_found"

    own = client.get("/api/v1/applications", headers=bakery).json()
    assert [a["id"] for a in own] == [app["id"]]
    assert own[0]["info_request"] is None


def test_patch_autosaves_and_bumps_version(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery)

    response = _patch(client, bakery, app, amount="3000000.00", term_months=12)

    assert response.status_code == 200
    saved = response.json()
    assert (saved["amount"], saved["term_months"], saved["version"]) == ("3000000.00", 12, 2)
    assert client.get(f"/api/v1/applications/{app['id']}", headers=bakery).json() == saved


def test_patch_with_stale_version_is_conflict(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery)
    assert _patch(client, bakery, app, term_months=12).status_code == 200

    stale = _patch(client, bakery, app, term_months=18)  # version всё ещё 1

    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"


def test_patch_null_clears_field(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery, amount="1000000.00")

    response = _patch(client, bakery, app, amount=None)

    assert response.json()["amount"] is None


def test_patch_rejects_unknown_fields_and_float_money(
    client: TestClient, bakery: dict[str, str]
) -> None:
    app = _create(client, bakery)

    assert _patch(client, bakery, app, status="APPROVED").status_code == 422
    float_money = _patch(client, bakery, app, amount=3000000.0)
    assert float_money.status_code == 422
    assert float_money.json()["field"] == "amount"


def test_submit_full_draft(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery)
    app = _patch(client, bakery, app, **BAKERY_DRAFT).json()

    response = client.post(
        f"/api/v1/applications/{app['id']}/submit",
        headers={**bakery, "Idempotency-Key": "k1"},
    )

    assert response.status_code == 200
    submitted = response.json()
    # submit сразу обрабатывает заявку: Пекарня по плану одобряется (R9).
    assert submitted["status"] == "APPROVED"
    assert submitted["submitted_at"] is not None
    assert submitted["status_changed_at"] >= submitted["submitted_at"]


@pytest.mark.parametrize(
    ("missing", "message_part"),
    [
        ("product_id", "продукт"),
        ("amount", "сумму"),
        ("term_months", "срок"),
        ("purpose", "цель"),
        ("revenue_12m", "выручку"),
        ("existing_payments_monthly", "платежи"),
    ],
)
def test_submit_requires_all_fields(
    client: TestClient, bakery: dict[str, str], missing: str, message_part: str
) -> None:
    app = _create(client, bakery)
    _patch(client, bakery, app, **{**BAKERY_DRAFT, missing: None})

    response = client.post(f"/api/v1/applications/{app['id']}/submit", headers=bakery)

    assert response.status_code == 422
    assert response.json()["field"] == missing
    assert message_part in response.json()["message"]


def test_submit_requires_bki_consent(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery)
    _patch(client, bakery, app, **{**BAKERY_DRAFT, "bki_consent": False})

    response = client.post(f"/api/v1/applications/{app['id']}/submit", headers=bakery)

    assert response.status_code == 422
    assert response.json()["field"] == "bki_consent"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount", "299999.99"),
        ("amount", "5000000.01"),
        ("term_months", 2),
        ("term_months", 25),
    ],
)
def test_submit_checks_product_limits(
    client: TestClient, bakery: dict[str, str], field: str, value: Any
) -> None:
    app = _create(client, bakery)
    _patch(client, bakery, app, **{**BAKERY_DRAFT, field: value})

    response = client.post(f"/api/v1/applications/{app['id']}/submit", headers=bakery)

    assert response.status_code == 422
    assert response.json()["field"] == field
    assert "Экспресс-оборот" in response.json()["message"]


def test_product_limit_boundaries_are_inclusive(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery)
    _patch(client, bakery, app, **{**BAKERY_DRAFT, "amount": "5000000.00", "term_months": 24})

    response = client.post(f"/api/v1/applications/{app['id']}/submit", headers=bakery)

    assert response.status_code == 200


def test_second_submit_and_edit_after_submit_are_conflicts(
    client: TestClient, bakery: dict[str, str]
) -> None:
    app = _create(client, bakery)
    app = _patch(client, bakery, app, **BAKERY_DRAFT).json()
    submitted = client.post(f"/api/v1/applications/{app['id']}/submit", headers=bakery).json()

    again = client.post(f"/api/v1/applications/{app['id']}/submit", headers=bakery)
    edit = _patch(client, bakery, submitted, amount="1000000.00")

    assert again.status_code == 409
    assert again.json()["code"] == "invalid_transition"
    assert edit.status_code == 409
    assert edit.json()["code"] == "conflict"


def test_history_records_every_status(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery)
    app = _patch(client, bakery, app, **BAKERY_DRAFT).json()
    client.post(f"/api/v1/applications/{app['id']}/submit", headers=bakery)

    response = client.get(f"/api/v1/applications/{app['id']}/history", headers=bakery)

    assert response.status_code == 200
    steps = [(h["from_status"], h["to_status"], h["actor_type"]) for h in response.json()]
    assert steps == [
        (None, "DRAFT", "client"),
        ("DRAFT", "SUBMITTED", "client"),
        ("SUBMITTED", "ENRICHMENT", "system"),
        ("ENRICHMENT", "SCORING", "system"),
        ("SCORING", "APPROVED", "system"),
    ]


def test_history_visibility(client: TestClient, bakery: dict[str, str]) -> None:
    app = _create(client, bakery)
    path = f"/api/v1/applications/{app['id']}/history"

    underwriter = auth_headers(client, "underwriter@demo.local")
    assert client.get(path, headers=underwriter).status_code == 200
    assert client.get(path, headers=auth_headers(client, "kovalev@demo.local")).status_code == 404
    assert client.get(path).status_code == 401


def test_unknown_application_is_404(client: TestClient, bakery: dict[str, str]) -> None:
    response = client.get(
        "/api/v1/applications/00000000-0000-4000-8000-000000000000", headers=bakery
    )

    assert response.status_code == 404

"""Подписание и выдача: код, подтверждение, SIGNING → SIGNED → ISSUED, попытки, срок, доступ."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from conftest import auth_headers
from demo_flows import BAKERY, KOVALEV, rows, steps, submit_demo
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import DisbursementRow, SignatureRow
from app.services.schedule import add_months
from app.services.signing import ACCOUNT_MASK, MAX_ATTEMPTS


def _accepted(client: TestClient, client_case) -> tuple[dict, dict]:  # noqa: ANN001
    app, headers = submit_demo(client, *client_case)
    response = client.post(
        f"/api/v1/applications/{app['id']}/offers/{app['active_offer']['id']}/accept",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json(), headers


def _code(client: TestClient, app: dict, headers: dict):  # noqa: ANN202
    return client.post(f"/api/v1/applications/{app['id']}/signing/code", headers=headers)


def _confirm(client: TestClient, app: dict, headers: dict, code: str):  # noqa: ANN202
    return client.post(
        f"/api/v1/applications/{app['id']}/signing/confirm",
        json={"code": code},
        headers={**headers, "Idempotency-Key": "sign-1"},
    )


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 10**6:06d}"


# ── Полный путь ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("client_case", "decided", "amount"),
    [(BAKERY, "APPROVED", "3000000.00"), (KOVALEV, "COUNTER_OFFER", "2000000.00")],
)
def test_confirm_signs_and_issues(
    client: TestClient, engine: Engine, client_case, decided: str, amount: str
) -> None:  # noqa: ANN001
    app, headers = _accepted(client, client_case)
    code = _code(client, app, headers).json()["code"]

    response = _confirm(client, app, headers, code)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ISSUED"
    assert body["active_offer"]["amount"] == amount
    assert steps(client, app, headers)[-3:] == [
        (decided, "SIGNING", "client"),
        ("SIGNING", "SIGNED", "client"),
        ("SIGNED", "ISSUED", "system"),
    ]
    [disbursement] = rows(engine, DisbursementRow, app["id"])
    assert disbursement.amount == Decimal(amount)
    assert disbursement.account_mask == ACCOUNT_MASK
    assert str(disbursement.offer_id) == app["active_offer"]["id"]
    [signature] = rows(engine, SignatureRow, app["id"])
    assert signature.signed_at is not None
    assert signature.code_hash != code  # хранится только HMAC


def test_code_is_six_digits_and_lives_five_minutes(client: TestClient) -> None:
    app, headers = _accepted(client, BAKERY)
    before = datetime.now(UTC)

    response = _code(client, app, headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["code"]) == 6 and body["code"].isdigit()
    expires = datetime.fromisoformat(body["expires_at"])
    assert before + timedelta(minutes=5) <= expires <= datetime.now(UTC) + timedelta(minutes=5)


def test_schedule_after_issuance_starts_from_issue_date(client: TestClient, engine: Engine) -> None:
    app, headers = _accepted(client, BAKERY)
    _confirm(client, app, headers, _code(client, app, headers).json()["code"])
    [disbursement] = rows(engine, DisbursementRow, app["id"])

    schedule = client.get(f"/api/v1/applications/{app['id']}/schedule", headers=headers).json()

    first_due = add_months(disbursement.executed_at.date(), 1)
    assert schedule["items"][0]["due_date"] == first_due.isoformat()
    assert len(schedule["items"]) == 12


# ── Неверный, истёкший, заменённый код ──────────────────────────────────────


def test_wrong_code_is_rejected_and_counted(client: TestClient, engine: Engine) -> None:
    app, headers = _accepted(client, BAKERY)
    code = _code(client, app, headers).json()["code"]

    response = _confirm(client, app, headers, _wrong(code))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_code"
    assert response.json()["field"] == "code"
    [signature] = rows(engine, SignatureRow, app["id"])
    assert signature.attempts == 1
    assert client.get(f"/api/v1/applications/{app['id']}", headers=headers).json()["status"] == (
        "SIGNING"
    )
    assert rows(engine, DisbursementRow, app["id"]) == []


def test_code_is_burnt_after_max_attempts(client: TestClient) -> None:
    app, headers = _accepted(client, BAKERY)
    code = _code(client, app, headers).json()["code"]
    for _ in range(MAX_ATTEMPTS):
        assert _confirm(client, app, headers, _wrong(code)).status_code == 422

    burnt = _confirm(client, app, headers, code)

    assert burnt.status_code == 422
    assert burnt.json()["code"] == "invalid_code"
    fresh = _code(client, app, headers).json()["code"]
    assert _confirm(client, app, headers, fresh).json()["status"] == "ISSUED"


def test_expired_code_is_rejected(client: TestClient, engine: Engine) -> None:
    app, headers = _accepted(client, BAKERY)
    code = _code(client, app, headers).json()["code"]
    with Session(engine) as session:
        row = session.scalars(
            select(SignatureRow).where(SignatureRow.application_id == UUID(app["id"]))
        ).one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    response = _confirm(client, app, headers, code)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_code"


def test_new_code_replaces_previous(client: TestClient, engine: Engine) -> None:
    app, headers = _accepted(client, BAKERY)
    first = _code(client, app, headers).json()["code"]
    second = _code(client, app, headers).json()["code"]
    assert len(rows(engine, SignatureRow, app["id"])) == 1

    if first != second:
        assert _confirm(client, app, headers, first).status_code == 422
    assert _confirm(client, app, headers, second).json()["status"] == "ISSUED"


def test_confirm_without_code_is_invalid_code(client: TestClient) -> None:
    app, headers = _accepted(client, BAKERY)

    response = _confirm(client, app, headers, "123456")

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_code"


@pytest.mark.parametrize("code", ["12345", "1234567", "12ab56", ""])
def test_malformed_code_is_validation_error(client: TestClient, code: str) -> None:
    app, headers = _accepted(client, BAKERY)
    _code(client, app, headers)

    response = _confirm(client, app, headers, code)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


# ── Статусы и доступ ────────────────────────────────────────────────────────


def test_code_before_accept_is_invalid_transition(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)
    assert app["status"] == "APPROVED"

    response = _code(client, app, headers)

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


def test_after_issuance_signing_is_closed(client: TestClient) -> None:
    app, headers = _accepted(client, BAKERY)
    code = _code(client, app, headers).json()["code"]
    _confirm(client, app, headers, code)

    again = _confirm(client, app, headers, code)
    new_code = _code(client, app, headers)

    assert again.status_code == 409
    assert again.json()["code"] == "invalid_transition"
    assert new_code.status_code == 409


def test_other_client_gets_404(client: TestClient) -> None:
    app, headers = _accepted(client, BAKERY)
    code = _code(client, app, headers).json()["code"]
    stranger = auth_headers(client, "stroy@demo.local")

    assert _code(client, app, stranger).status_code == 404
    assert _confirm(client, app, stranger, code).status_code == 404


def test_underwriter_cannot_sign(client: TestClient) -> None:
    app, headers = _accepted(client, BAKERY)
    underwriter = auth_headers(client, "underwriter@demo.local")

    assert _code(client, app, underwriter).status_code == 403
    assert _confirm(client, app, underwriter, "123456").status_code == 403

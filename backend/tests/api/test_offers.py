"""accept / decline оффера и cancel заявки: переходы, связь оффера с заявкой, повторы, доступ."""

from uuid import UUID

import pytest
from conftest import auth_headers
from demo_flows import BAKERY, KOVALEV, MELNIKOVA, create_draft, rows, steps, submit_demo
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.models import Application, OfferRow


def _answer(client: TestClient, app: dict, headers: dict, verb: str, offer_id: str | None = None):  # noqa: ANN202
    offer_id = offer_id or app["active_offer"]["id"]
    return client.post(
        f"/api/v1/applications/{app['id']}/offers/{offer_id}/{verb}",
        headers={**headers, "Idempotency-Key": f"{verb}-1"},
    )


# ── accept ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("client_case", "decided"), [(BAKERY, "APPROVED"), (KOVALEV, "COUNTER_OFFER")]
)
def test_accept_moves_to_signing(
    client: TestClient, engine: Engine, client_case, decided: str
) -> None:  # noqa: ANN001
    app, headers = submit_demo(client, *client_case)
    assert app["status"] == decided

    response = _answer(client, app, headers, "accept")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SIGNING"
    # Контракт: после принятия поле не обнуляется — условия нужны на подписании и выдаче.
    assert body["active_offer"]["id"] == app["active_offer"]["id"]
    assert body["active_offer"]["status"] == "accepted"
    assert steps(client, app, headers)[-2:] == [
        ("SCORING", decided, "system"),
        (decided, "SIGNING", "client"),
    ]
    [offer] = rows(engine, OfferRow, app["id"])
    assert offer.status == "accepted"


def test_second_accept_is_offer_not_active(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)
    _answer(client, app, headers, "accept")

    again = _answer(client, app, headers, "accept")

    assert again.status_code == 409
    assert again.json()["code"] == "offer_not_active"


# ── decline ─────────────────────────────────────────────────────────────────


def test_decline_closes_application(client: TestClient, engine: Engine) -> None:
    app, headers = submit_demo(client, *KOVALEV)

    response = _answer(client, app, headers, "decline")

    assert response.status_code == 200
    assert response.json()["status"] == "DECLINED_BY_CLIENT"
    assert response.json()["active_offer"]["status"] == "declined"
    assert steps(client, app, headers)[-1] == ("COUNTER_OFFER", "DECLINED_BY_CLIENT", "client")
    [offer] = rows(engine, OfferRow, app["id"])
    assert offer.status == "declined"


def test_cannot_accept_after_decline(client: TestClient) -> None:
    app, headers = submit_demo(client, *KOVALEV)
    _answer(client, app, headers, "decline")

    response = _answer(client, app, headers, "accept")

    assert response.status_code == 409
    assert response.json()["code"] == "offer_not_active"


# ── связь оффера с заявкой и доступ ─────────────────────────────────────────


def test_offer_of_another_application_is_404(client: TestClient) -> None:
    first, headers = submit_demo(client, *BAKERY)
    second, _ = submit_demo(client, *BAKERY)

    response = _answer(client, first, headers, "accept", offer_id=second["active_offer"]["id"])

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_unknown_offer_is_404(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)

    response = _answer(client, app, headers, "accept", offer_id=str(UUID(int=7)))

    assert response.status_code == 404


def test_application_without_offer_has_nothing_to_accept(client: TestClient) -> None:
    app, headers = submit_demo(client, *MELNIKOVA)  # INFO_REQUESTED — оффера нет

    assert app["active_offer"] is None
    assert _answer(client, app, headers, "accept", offer_id=str(UUID(int=7))).status_code == 404


def test_other_company_cannot_answer_offer(client: TestClient) -> None:
    app, _ = submit_demo(client, *BAKERY)

    response = _answer(client, app, auth_headers(client, "kovalev@demo.local"), "accept")

    assert response.status_code == 404


def test_bank_staff_cannot_answer_for_client(client: TestClient) -> None:
    app, _ = submit_demo(client, *BAKERY)

    response = _answer(client, app, auth_headers(client, "underwriter@demo.local"), "accept")

    assert response.status_code == 403


def test_active_offer_in_wrong_status_is_invalid_transition(
    client: TestClient, engine: Engine
) -> None:
    # Такого в нормальном пути нет, но правило перехода должно сработать само по себе.
    app, headers = submit_demo(client, *BAKERY)
    with Session(engine) as session:
        session.get(Application, UUID(app["id"])).status = "MANUAL_REVIEW"
        session.commit()

    response = _answer(client, app, headers, "accept")

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"
    [offer] = rows(engine, OfferRow, app["id"])
    assert offer.status == "active"  # оффер не тронут: изменения откатились


# ── cancel ──────────────────────────────────────────────────────────────────


def _cancel(client: TestClient, app: dict, headers: dict):  # noqa: ANN202
    return client.post(f"/api/v1/applications/{app['id']}/cancel", headers=headers)


def test_cancel_draft(client: TestClient) -> None:
    app, headers = create_draft(client, *BAKERY)

    response = _cancel(client, app, headers)

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert steps(client, app, headers)[-1] == ("DRAFT", "CANCELLED", "client")


def test_cancel_while_documents_requested_hides_request(client: TestClient) -> None:
    app, headers = submit_demo(client, *MELNIKOVA)
    assert app["info_request"] is not None

    response = _cancel(client, app, headers)

    assert response.json()["status"] == "CANCELLED"
    assert response.json()["info_request"] is None  # банк больше ничего не ждёт


@pytest.mark.parametrize("client_case", [BAKERY, KOVALEV])
def test_cancel_after_decision_is_invalid_transition(client: TestClient, client_case) -> None:  # noqa: ANN001
    app, headers = submit_demo(client, *client_case)

    response = _cancel(client, app, headers)

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


def test_second_cancel_is_invalid_transition(client: TestClient) -> None:
    app, headers = create_draft(client, *BAKERY)
    _cancel(client, app, headers)

    assert _cancel(client, app, headers).status_code == 409


def test_other_company_cannot_cancel(client: TestClient) -> None:
    app, _ = create_draft(client, *BAKERY)

    response = _cancel(client, app, auth_headers(client, "kovalev@demo.local"))

    assert response.status_code == 404

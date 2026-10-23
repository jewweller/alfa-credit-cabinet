"""GET /applications/{id}/schedule — график по офферу (временные правила B8)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from conftest import auth_headers
from demo_flows import BAKERY, KOVALEV, MELNIKOVA, submit_demo
from fastapi.testclient import TestClient

from app.services.schedule import add_months


def _schedule(client: TestClient, app: dict, headers: dict, **params: str):  # noqa: ANN202
    return client.get(f"/api/v1/applications/{app['id']}/schedule", params=params, headers=headers)


def test_schedule_of_approved_offer(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)

    response = _schedule(client, app, headers)

    assert response.status_code == 200
    body = response.json()
    offer = app["active_offer"]
    assert body["offer_id"] == offer["id"]
    assert (body["amount"], body["term_months"], body["rate"], body["monthly_payment"]) == (
        "3000000.00", 12, "18.00", "275039.98",
    )  # fmt: skip
    items = body["items"]
    assert len(items) == 12
    assert sum(Decimal(i["principal"]) for i in items) == Decimal("3000000")
    assert items[-1]["balance"] == "0.00"
    assert Decimal(body["total_payment"]) == sum(Decimal(i["payment"]) for i in items)
    assert Decimal(body["overpayment"]) == Decimal(body["total_payment"]) - Decimal("3000000")
    today = datetime.now(UTC).date()
    assert items[0]["due_date"] == add_months(today, 1).isoformat()
    assert items[-1]["due_date"] == add_months(today, 12).isoformat()


def test_schedule_of_counter_offer_uses_offered_terms(client: TestClient) -> None:
    app, headers = submit_demo(client, *KOVALEV)

    body = _schedule(client, app, headers).json()

    assert (body["term_months"], body["rate"], body["monthly_payment"]) == (
        24,
        "20.00",
        "101791.61",
    )
    assert len(body["items"]) == 24


def test_schedule_after_accept_is_still_available(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)
    offer_id = app["active_offer"]["id"]
    client.post(f"/api/v1/applications/{app['id']}/offers/{offer_id}/accept", headers=headers)

    response = _schedule(client, app, headers)

    assert response.status_code == 200
    assert response.json()["offer_id"] == offer_id


def test_explicit_offer_id(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)

    response = _schedule(client, app, headers, offer_id=app["active_offer"]["id"])

    assert response.status_code == 200


def test_offer_of_another_application_is_404(client: TestClient) -> None:
    first, headers = submit_demo(client, *BAKERY)
    second, _ = submit_demo(client, *BAKERY)

    response = _schedule(client, first, headers, offer_id=second["active_offer"]["id"])

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_application_without_offer_is_404(client: TestClient) -> None:
    app, headers = submit_demo(client, *MELNIKOVA)

    assert _schedule(client, app, headers).status_code == 404


def test_schedule_access(client: TestClient) -> None:
    app, _ = submit_demo(client, *BAKERY)

    assert _schedule(client, app, auth_headers(client, "kovalev@demo.local")).status_code == 404
    assert _schedule(client, app, auth_headers(client, "underwriter@demo.local")).status_code == 403
    assert _schedule(client, app, {}).status_code == 401
    assert _schedule(client, app, auth_headers(client), offer_id="nope").status_code == 422


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 10, 23), 3, date(2027, 1, 23)),
        (date(2026, 8, 31), 13, date(2027, 9, 30)),
    ],
)
def test_add_months_keeps_day_or_month_end(start: date, months: int, expected: date) -> None:
    assert add_months(start, months) == expected


def test_unknown_application_is_404(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/applications/{UUID(int=3)}/schedule", headers=auth_headers(client)
    )

    assert response.status_code == 404

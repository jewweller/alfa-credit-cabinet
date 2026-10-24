"""Подбор продукта: фильтр по цели, приведение к лимитам, примерный платёж, порядок, ошибки."""

import pytest
from conftest import auth_headers
from fastapi.testclient import TestClient


def _recommend(client: TestClient, body: dict, email: str = "bakery@demo.local"):  # noqa: ANN202
    return client.post("/api/v1/products/recommend", json=body, headers=auth_headers(client, email))


def _annuity(amount: float, rate_pct: float, months: int) -> str:
    """Независимый расчёт для проверки: аннуитет, до копейки."""
    r = rate_pct / 12 / 100
    return f"{amount * r / (1 - (1 + r) ** -months):.2f}"


def _brief(items: list[dict]) -> list[tuple]:
    return [(i["product"]["code"], i["amount"], i["term_months"], i["adjusted"]) for i in items]


def test_bakery_request_matches_plan_payment(client: TestClient) -> None:
    response = _recommend(
        client, {"purpose": "working_capital", "amount": "3000000.00", "term_months": 12}
    )

    assert response.status_code == 200
    [only] = response.json()
    assert only["product"]["code"] == "EXPRESS_WC"
    assert only["rate"] == "18.00"
    assert only["monthly_payment"] == "275039.98"  # как в разделе 8 плана и в решении R10
    assert only["adjusted"] == []


def test_fitting_products_go_first_then_cheaper(client: TestClient) -> None:
    response = _recommend(
        client, {"purpose": "cash_gap", "amount": "2000000.00", "term_months": 12}
    )

    items = response.json()
    assert _brief(items) == [
        ("EXPRESS_WC", "2000000.00", 12, []),
        ("OVERDRAFT", "2000000.00", 12, []),
    ]
    assert items[0]["monthly_payment"] == _annuity(2_000_000, 18, 12)
    assert items[1]["monthly_payment"] == _annuity(2_000_000, 20, 12)


def test_adjusted_product_goes_after_fitting_one(client: TestClient) -> None:
    response = _recommend(client, {"purpose": "cash_gap", "amount": "500000.00", "term_months": 6})

    assert _brief(response.json()) == [
        ("EXPRESS_WC", "500000.00", 6, []),
        ("OVERDRAFT", "500000.00", 12, ["term_months"]),
    ]


def test_amount_and_term_are_clamped_to_product_limits(client: TestClient) -> None:
    response = _recommend(client, {"purpose": "equipment", "amount": "500000.00", "term_months": 6})

    [item] = response.json()
    assert _brief([item]) == [("EQUIPMENT", "1000000.00", 12, ["amount", "term_months"])]
    assert item["monthly_payment"] == _annuity(1_000_000, 16, 12)


def test_amount_above_limit_is_lowered(client: TestClient) -> None:
    response = _recommend(
        client, {"purpose": "cash_gap", "amount": "4000000.00", "term_months": 12}
    )

    assert _brief(response.json()) == [
        ("EXPRESS_WC", "4000000.00", 12, []),
        ("OVERDRAFT", "3000000.00", 12, ["amount"]),
    ]


def test_bank_staff_can_use_calculator(client: TestClient) -> None:
    body = {"purpose": "working_capital", "amount": "1000000.00", "term_months": 12}

    assert _recommend(client, body, "underwriter@demo.local").status_code == 200


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"purpose": "yacht", "amount": "1000000.00", "term_months": 12}, "purpose"),
        ({"purpose": "equipment", "amount": "0.00", "term_months": 12}, "amount"),
        ({"purpose": "equipment", "amount": "100.5", "term_months": 12}, "amount"),
        ({"purpose": "equipment", "amount": "1000000.00", "term_months": 0}, "term_months"),
        ({"purpose": "equipment", "amount": "1000000.00"}, "term_months"),
    ],
)
def test_invalid_request_is_422_with_field(client: TestClient, body: dict, field: str) -> None:
    response = _recommend(client, body)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["field"] == field


def test_unknown_field_is_rejected(client: TestClient) -> None:
    body = {"purpose": "equipment", "amount": "1000000.00", "term_months": 12, "rate": "1.00"}

    assert _recommend(client, body).status_code == 422


def test_requires_login(client: TestClient) -> None:
    body = {"purpose": "equipment", "amount": "1000000.00", "term_months": 12}

    response = client.post("/api/v1/products/recommend", json=body)

    assert response.status_code == 401

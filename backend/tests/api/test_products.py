from conftest import auth_headers
from fastapi.testclient import TestClient


def test_products_require_login(client: TestClient) -> None:
    assert client.get("/api/v1/products").status_code == 401


def test_products_are_the_three_plan_products(client: TestClient) -> None:
    response = client.get("/api/v1/products", headers=auth_headers(client))

    assert response.status_code == 200
    by_code = {p["code"]: p for p in response.json()}
    assert set(by_code) == {"EXPRESS_WC", "EQUIPMENT", "OVERDRAFT"}
    # docs/plan.md, раздел 7: лимиты и базовые ставки.
    express = by_code["EXPRESS_WC"]
    assert (express["min_amount"], express["max_amount"]) == ("300000.00", "5000000.00")
    assert (express["min_term"], express["max_term"], express["base_rate"]) == (3, 24, "18.00")
    assert by_code["EQUIPMENT"]["base_rate"] == "16.00"
    assert by_code["OVERDRAFT"]["max_term"] == 12
    assert express["purpose_tags"] == ["working_capital", "cash_gap"]

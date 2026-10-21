"""Контракт первой волны: пути из плана (раздел 10), формат ошибок, актуальность openapi.json."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.openapi import CONTRACT_PATH, PLANNED, build_contract_openapi, render_contract

PLANNED_OPERATIONS = {
    ("post", "/api/v1/auth/login"),
    ("get", "/api/v1/auth/me"),
    ("get", "/api/v1/products"),
    ("get", "/api/v1/companies/lookup"),
    ("get", "/api/v1/applications"),
    ("post", "/api/v1/applications"),
    ("get", "/api/v1/applications/{id}"),
    ("patch", "/api/v1/applications/{id}"),
    ("post", "/api/v1/applications/{id}/submit"),
}
IMPLEMENTED_OPERATIONS = {("get", "/health"), ("get", "/api/v1/health")}
PUBLIC_OPERATIONS = {("post", "/api/v1/auth/login"), *IMPLEMENTED_OPERATIONS}


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return build_contract_openapi(create_app())


def _operations(spec: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (method, path): operation
        for path, operations in spec["paths"].items()
        for method, operation in operations.items()
    }


def test_contract_contains_exactly_planned_and_implemented_operations(spec: dict) -> None:
    assert set(_operations(spec)) == PLANNED_OPERATIONS | IMPLEMENTED_OPERATIONS


def test_api_paths_use_v1_prefix(spec: dict) -> None:
    for path in spec["paths"]:
        assert path == "/health" or path.startswith("/api/v1/")


def test_implementation_status_marks(spec: dict) -> None:
    for key, operation in _operations(spec).items():
        expected = PLANNED if key in PLANNED_OPERATIONS else "implemented"
        assert operation["x-implementation-status"] == expected, key
        if expected == PLANNED:
            assert operation["description"].startswith("**Только контракт")


def test_all_error_responses_use_error_schema(spec: dict) -> None:
    for key, operation in _operations(spec).items():
        for status_code, response in operation["responses"].items():
            if int(status_code) >= 400:
                schema = response["content"]["application/json"]["schema"]
                assert schema == {"$ref": "#/components/schemas/ErrorResponse"}, (key, status_code)
    assert "HTTPValidationError" not in spec["components"]["schemas"]


def test_protected_operations_require_bearer(spec: dict) -> None:
    for key, operation in _operations(spec).items():
        has_security = bool(operation.get("security"))
        assert has_security is (key not in PUBLIC_OPERATIONS), key


def test_submit_accepts_idempotency_key(spec: dict) -> None:
    operation = spec["paths"]["/api/v1/applications/{id}/submit"]["post"]
    headers = [p["name"] for p in operation["parameters"] if p["in"] == "header"]
    assert headers == ["Idempotency-Key"]


def test_money_and_rate_are_strings(spec: dict) -> None:
    product = spec["components"]["schemas"]["Product"]["properties"]
    for field in ("min_amount", "max_amount", "base_rate"):
        assert product[field]["type"] == "string"
        assert product[field]["pattern"] == r"^\d+\.\d{2}$"
    assert "в процентах" in product["base_rate"]["description"]


def test_planned_operations_are_not_served_by_app() -> None:
    app = create_app()
    client = TestClient(app)

    assert set(app.openapi()["paths"]) == {"/health", "/api/v1/health"}
    response = client.get("/api/v1/applications")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_contract_file_is_up_to_date() -> None:
    assert CONTRACT_PATH.exists(), "выполните `uv run python -m app.openapi`"
    assert CONTRACT_PATH.read_text(encoding="utf-8") == render_contract(create_app()), (
        "docs/api/openapi.json устарел: выполните `uv run python -m app.openapi`"
    )

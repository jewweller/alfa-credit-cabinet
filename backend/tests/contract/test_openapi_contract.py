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
    ("post", "/api/v1/products/recommend"),
    ("get", "/api/v1/companies/lookup"),
    ("get", "/api/v1/applications"),
    ("post", "/api/v1/applications"),
    ("get", "/api/v1/applications/{id}"),
    ("patch", "/api/v1/applications/{id}"),
    ("post", "/api/v1/applications/{id}/submit"),
    ("get", "/api/v1/applications/{id}/history"),
    ("post", "/api/v1/applications/{id}/offers/{offer_id}/accept"),
    ("post", "/api/v1/applications/{id}/offers/{offer_id}/decline"),
    ("get", "/api/v1/applications/{id}/schedule"),
    ("post", "/api/v1/applications/{id}/documents"),
    ("get", "/api/v1/documents/{id}"),
    ("post", "/api/v1/applications/{id}/resubmit"),
    ("post", "/api/v1/applications/{id}/cancel"),
    ("post", "/api/v1/applications/{id}/signing/code"),
    ("post", "/api/v1/applications/{id}/signing/confirm"),
}
IDEMPOTENT_OPERATIONS = {
    ("post", "/api/v1/applications/{id}/submit"),
    ("post", "/api/v1/applications/{id}/offers/{offer_id}/accept"),
    ("post", "/api/v1/applications/{id}/offers/{offer_id}/decline"),
    ("post", "/api/v1/applications/{id}/resubmit"),
    ("post", "/api/v1/applications/{id}/cancel"),
    ("post", "/api/v1/applications/{id}/signing/confirm"),
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


@pytest.mark.parametrize(("method", "path"), sorted(IDEMPOTENT_OPERATIONS))
def test_state_changing_operations_accept_idempotency_key(
    spec: dict, method: str, path: str
) -> None:
    operation = spec["paths"][path][method]
    headers = [p["name"] for p in operation["parameters"] if p["in"] == "header"]
    assert headers == ["Idempotency-Key"]


def test_upload_document_is_multipart_with_file_and_kind(spec: dict) -> None:
    operation = spec["paths"]["/api/v1/applications/{id}/documents"]["post"]
    content = operation["requestBody"]["content"]
    assert list(content) == ["multipart/form-data"]

    ref = content["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
    body = spec["components"]["schemas"][ref]
    # OpenAPI 3.1: файл описывается через contentMediaType, а не format: binary.
    assert body["properties"]["file"]["contentMediaType"] == "application/octet-stream"
    assert set(body["required"]) == {"file", "kind"}
    assert {"201", "413", "415"} <= set(operation["responses"])


def test_download_document_returns_binary_file(spec: dict) -> None:
    content = spec["paths"]["/api/v1/documents/{id}"]["get"]["responses"]["200"]["content"]
    assert set(content) == {"application/pdf", "image/jpeg", "image/png"}
    for media in content.values():
        assert media["schema"] == {"type": "string", "format": "binary"}


def test_reject_reasons_are_explained_by_engine_rules(spec: dict) -> None:
    reason = spec["components"]["schemas"]["RejectReason"]
    descriptions = dict(zip(reason["enum"], reason["x-enum-descriptions"], strict=True))

    assert descriptions["company_inactive"].startswith("R1, компания ликвидирована")
    assert descriptions["bankruptcy_or_overdue"].startswith("R2,")
    assert descriptions["low_score"].startswith("R6,")
    assert descriptions["no_suitable_terms"].startswith("R10,")
    assert "специалиста" in descriptions["underwriter_decision"]
    for code, text in descriptions.items():
        assert f"`{code}` — {text}" in reason["description"]


def test_application_card_carries_everything_c5_needs(spec: dict) -> None:
    detail = spec["components"]["schemas"]["ApplicationDetail"]["properties"]
    assert {"status_changed_at", "decision", "info_request", "documents"} <= set(detail)
    summary = spec["components"]["schemas"]["ApplicationSummary"]["properties"]
    assert {"status_changed_at", "info_request"} <= set(summary)


def test_me_returns_company_for_header(spec: dict) -> None:
    me = spec["components"]["schemas"]["MeResponse"]["properties"]
    assert "company" in me
    assert "company_id" not in me


def test_money_and_rate_are_strings(spec: dict) -> None:
    product = spec["components"]["schemas"]["Product"]["properties"]
    for field in ("min_amount", "max_amount", "base_rate"):
        assert product[field]["type"] == "string"
        assert product[field]["pattern"] == r"^\d+\.\d{2}$"
    assert "в процентах" in product["base_rate"]["description"]

    schedule = spec["components"]["schemas"]["PaymentScheduleItem"]["properties"]
    for field in ("payment", "principal", "interest", "balance"):
        assert schedule[field]["type"] == "string", field


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

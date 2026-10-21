"""Все ошибки отдаются в формате {code, message, field?}. Тестовые маршруты — только здесь."""

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.domain.state_machine import ApplicationStatus, ensure_transition
from app.main import create_app
from app.schemas.common import Money


class _Body(BaseModel):
    amount: Money


def _app_with_test_routes() -> FastAPI:
    app = create_app()

    @app.post("/_test/body")
    def body_route(body: _Body) -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/_test/forbidden")
    def forbidden_route() -> None:
        raise HTTPException(status_code=403, detail="Нет доступа")

    @app.get("/_test/transition")
    def transition_route() -> None:
        ensure_transition(ApplicationStatus.DRAFT, ApplicationStatus.ISSUED)

    return app


client = TestClient(_app_with_test_routes())


def test_validation_error_points_to_field() -> None:
    response = client.post("/_test/body", json={"amount": 100})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["field"] == "amount"
    assert body["message"]


def test_unknown_path_is_not_found_without_field() -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not Found"}


def test_http_exception_keeps_detail_as_message() -> None:
    response = client.get("/_test/forbidden")

    assert response.status_code == 403
    assert response.json() == {"code": "forbidden", "message": "Нет доступа"}


def test_invalid_transition_maps_to_409() -> None:
    response = client.get("/_test/transition")

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"

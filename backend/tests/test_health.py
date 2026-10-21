from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_swagger_and_openapi_are_served_under_api_prefix() -> None:
    client = TestClient(create_app())

    assert client.get("/api/docs").status_code == 200
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    assert "/health" in schema.json()["paths"]

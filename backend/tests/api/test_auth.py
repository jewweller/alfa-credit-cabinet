from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from conftest import DEMO_PASSWORD, auth_headers
from fastapi.testclient import TestClient

from app.security import create_access_token

BAKERY_USER = UUID("5a0e7d6c-0000-4000-8000-0000000000aa")


def test_login_returns_bearer_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "bakery@demo.local", "password": DEMO_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2


def test_login_email_is_case_insensitive(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "Bakery@Demo.Local", "password": DEMO_PASSWORD}
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("email", "password"),
    [("bakery@demo.local", "wrong"), ("nobody@demo.local", DEMO_PASSWORD)],
)
def test_login_rejects_wrong_password_and_unknown_email_the_same_way(
    client: TestClient, email: str, password: str
) -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json() == {"code": "unauthorized", "message": "Неверный email или пароль"}


def test_login_validates_body(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "bakery@demo.local"})

    assert response.status_code == 422
    assert response.json()["field"] == "password"


def test_me_returns_client_with_company(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers(client))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(BAKERY_USER),
        "email": "bakery@demo.local",
        "full_name": "Ирина Соколова",
        "role": "client",
        "company": {
            "id": "5a0e7d6c-0000-4000-8000-0000000000cc",
            "inn": "7701000019",
            "name": "ООО «Пекарня Север»",
            "kind": "LLC",
            "okved_main": "10.71",
            "segment": "small",
        },
    }


def test_me_for_bank_staff_has_no_company(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_headers(client, "underwriter@demo.local"))

    assert response.status_code == 200
    assert response.json()["role"] == "underwriter"
    assert response.json()["company"] is None


def test_me_without_token_is_401_with_challenge(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        create_access_token(BAKERY_USER, "client")[:-2] + "xx",  # подпись испорчена
        create_access_token(BAKERY_USER, "client", now=datetime.now(UTC) - timedelta(days=2)),
        create_access_token(UUID(int=1), "client"),  # такого пользователя нет
    ],
    ids=["garbage", "tampered", "expired", "unknown-user"],
)
def test_me_rejects_invalid_tokens(client: TestClient, token: str) -> None:
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"

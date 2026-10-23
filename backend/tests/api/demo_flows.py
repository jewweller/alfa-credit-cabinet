"""Общие шаги сквозных API-тестов: демо-клиенты, отправка заявки, чтение результатов из БД.

Анкеты — docs/plan.md, раздел 7; данные источников — mocks/fixtures (черновик).
"""

from typing import Any
from uuid import UUID

from conftest import auth_headers
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

EXPRESS_WC = "7f1c2b0a-0000-4000-8000-000000000001"


def draft(amount: str, revenue: str, payments: str, term: int = 12) -> dict[str, Any]:
    return {
        "product_id": EXPRESS_WC,
        "amount": amount,
        "term_months": term,
        "purpose": "working_capital",
        "revenue_12m": revenue,
        "existing_payments_monthly": payments,
        "bki_consent": True,
    }


# Анкеты из docs/plan.md, раздел 7.
BAKERY = ("bakery@demo.local", draft("3000000.00", "24000000.00", "150000.00"))
KOVALEV = ("kovalev@demo.local", draft("2000000.00", "6000000.00", "60000.00"))
MELNIKOVA = ("melnikova@demo.local", draft("1500000.00", "12000000.00", "0.00"))
# Анкеты СтройРесурса в плане нет (D7): значения произвольные, исход определяет R1.
STROY = ("stroy@demo.local", draft("2000000.00", "9000000.00", "0.00"))

PIPELINE_STEPS = [
    (None, "DRAFT", "client"),
    ("DRAFT", "SUBMITTED", "client"),
    ("SUBMITTED", "ENRICHMENT", "system"),
    ("ENRICHMENT", "SCORING", "system"),
]


def create_draft(client: TestClient, email: str, body: dict[str, Any]) -> tuple[dict, dict]:
    headers = auth_headers(client, email)
    created = client.post("/api/v1/applications", json={}, headers=headers).json()
    patched = client.patch(
        f"/api/v1/applications/{created['id']}",
        json={"version": created["version"], **body},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    return patched.json(), headers


def submit_demo(client: TestClient, email: str, body: dict[str, Any]) -> tuple[dict, dict]:
    created, headers = create_draft(client, email, body)
    response = client.post(f"/api/v1/applications/{created['id']}/submit", headers=headers)
    assert response.status_code == 200, response.text
    return response.json(), headers


def rows(engine: Engine, model: type, application_id: str) -> list:
    with Session(engine) as session:
        query = select(model).where(model.application_id == UUID(application_id))
        return list(session.scalars(query))


def steps(client: TestClient, app: dict, headers: dict) -> list[tuple]:
    history = client.get(f"/api/v1/applications/{app['id']}/history", headers=headers).json()
    return [(h["from_status"], h["to_status"], h["actor_type"]) for h in history]

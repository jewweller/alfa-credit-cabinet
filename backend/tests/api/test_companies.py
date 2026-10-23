"""GET /api/v1/companies/lookup — автозаполнение по ИНН из ЕГРЮЛ / ЕГРИП (фикстуры mocks)."""

import pytest
from conftest import auth_headers
from fastapi.testclient import TestClient

from app.integrations.base import FetchResult
from app.integrations.fixtures import get_source_client
from app.scoring.inputs import SourceState

LOOKUP = "/api/v1/companies/lookup"
FIELDS = {
    "inn", "kind", "ogrn", "name", "status", "registered_at", "okved_main", "okved_extra",
    "region", "address", "director_fio",
}  # fmt: skip


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(client)


def test_llc_from_egrul(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(LOOKUP, params={"inn": "7701000019"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == FIELDS  # ровно схема CompanyLookupResponse, без служебных полей фикстуры
    assert body == {
        "inn": "7701000019",
        "kind": "LLC",
        "ogrn": "1187746000019",
        "name": "ООО «Пекарня Север»",
        "status": "ACTIVE",
        "registered_at": "2018-09-14",
        "okved_main": "10.71",
        "okved_extra": ["10.72", "47.24"],
        "region": "Москва",
        "address": "г. Москва, ул. Северная, д. 12",
        "director_fio": "Соколова Ирина Павловна",
    }


def test_entrepreneur_from_egrip_is_normalized(client: TestClient, headers: dict[str, str]) -> None:
    body = client.get(LOOKUP, params={"inn": "500100001072"}, headers=headers).json()

    assert (body["kind"], body["ogrn"], body["name"]) == (
        "IE", "321500100001072", "Ковалёв Андрей Сергеевич",
    )  # fmt: skip
    assert (body["okved_extra"], body["address"], body["director_fio"]) == ([], None, None)


def test_liquidated_company_is_still_found(client: TestClient, headers: dict[str, str]) -> None:
    # Автозаполнение показывает статус как есть; отказ — дело правила R1 после отправки.
    body = client.get(LOOKUP, params={"inn": "7701000026"}, headers=headers).json()

    assert body["status"] == "LIQUIDATED"


def test_inn_missing_in_registry_is_404(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(LOOKUP, params={"inn": "7701000072"}, headers=headers)

    assert response.status_code == 404
    assert response.json() == {
        "code": "company_not_found",
        "message": "Компания с таким ИНН не найдена в ЕГРЮЛ",
    }


@pytest.mark.parametrize("inn", ["123", "77010000190", "770100001a", ""])
def test_malformed_inn_is_422(client: TestClient, headers: dict[str, str], inn: str) -> None:
    response = client.get(LOOKUP, params={"inn": inn}, headers=headers)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["field"] == "inn"


def test_missing_inn_parameter_is_422(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(LOOKUP, headers=headers)

    assert response.status_code == 422
    assert response.json()["field"] == "inn"


class _RegistryDown:
    def fetch(self, source: str, inn: str) -> FetchResult:
        return FetchResult(source, SourceState.UNAVAILABLE, attempts=3, error="timeout")


def test_unavailable_registry_is_503(client: TestClient, headers: dict[str, str]) -> None:
    client.app.dependency_overrides[get_source_client] = _RegistryDown  # type: ignore[attr-defined]

    response = client.get(LOOKUP, params={"inn": "500100001072"}, headers=headers)

    assert response.status_code == 503
    assert response.json() == {
        "code": "upstream_unavailable",
        "message": "ЕГРИП сейчас не отвечает, попробуйте позже",
    }


def test_lookup_requires_login(client: TestClient) -> None:
    response = client.get(LOOKUP, params={"inn": "7701000019"})

    assert response.status_code == 401


def test_bank_staff_can_lookup(client: TestClient) -> None:
    headers = auth_headers(client, "underwriter@demo.local")

    assert client.get(LOOKUP, params={"inn": "7701000019"}, headers=headers).status_code == 200


@pytest.mark.parametrize("inn", ["7701000033", "7701000058", "7701000065"])
def test_other_plan_inns_are_in_registry(
    client: TestClient, headers: dict[str, str], inn: str
) -> None:
    assert client.get(LOOKUP, params={"inn": inn}, headers=headers).status_code == 200

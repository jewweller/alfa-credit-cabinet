"""Журнал действий и сброс демо: что пишется, кем, фильтры, доступ, сброс."""

from pathlib import Path

import pytest
from conftest import DEMO_PASSWORD, auth_headers
from demo_flows import BAKERY, KOVALEV, MELNIKOVA, MIRAGE, create_draft, submit_demo
from fastapi.testclient import TestClient

from app.config import get_settings
from app.storage import LocalStorage, get_storage

UNDERWRITER = "underwriter@demo.local"
ADMIN = "admin@demo.local"
PDF = b"%PDF-1.7\n% demo declaration\n"


@pytest.fixture
def storage(client: TestClient, tmp_path: Path) -> Path:
    client.app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)  # type: ignore[attr-defined]
    return tmp_path


@pytest.fixture
def demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "demo_mode", True)


def _audit(client: TestClient, email: str = ADMIN, **params) -> list[dict]:  # noqa: ANN003
    response = client.get("/api/v1/bank/audit", params=params, headers=auth_headers(client, email))
    assert response.status_code == 200, response.text
    return response.json()


def _trail(client: TestClient, app: dict) -> list[tuple[str, str, str]]:
    """Действия по заявке от старых к новым: (действие, роль, summary)."""
    rows = _audit(client, application_id=app["id"])
    return [(r["action"], r["actor_role"], r["summary"]) for r in reversed(rows)]


def _reset(client: TestClient, email: str = ADMIN):  # noqa: ANN202
    return client.post("/api/v1/admin/demo/reset", headers=auth_headers(client, email))


# ── Что пишется ─────────────────────────────────────────────────────────────


def test_client_path_to_issuance_is_fully_logged(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)
    offer = app["active_offer"]["id"]
    client.post(f"/api/v1/applications/{app['id']}/offers/{offer}/accept", headers=headers)
    code = client.post(f"/api/v1/applications/{app['id']}/signing/code", headers=headers).json()
    client.post(
        f"/api/v1/applications/{app['id']}/signing/confirm",
        json={"code": code["code"]},
        headers=headers,
    )

    trail = _trail(client, app)

    assert [(a, r) for a, r, _ in trail] == [
        ("application.created", "client"),
        ("application.submitted", "client"),
        ("application.status_changed", "system"),
        ("application.status_changed", "system"),
        ("application.status_changed", "system"),
        ("offer.accepted", "client"),
        ("signing.code_issued", "client"),
        ("signing.confirmed", "client"),
        ("loan.issued", "system"),
    ]
    assert [s for _, _, s in trail][1:6] == [
        "DRAFT → SUBMITTED",
        "SUBMITTED → ENRICHMENT",
        "ENRICHMENT → SCORING",
        "SCORING → APPROVED",
        "APPROVED → SIGNING",
    ]
    rows = {r["action"]: r for r in _audit(client, application_id=app["id"])}
    assert rows["offer.accepted"]["details"]["offer_id"] == offer
    assert rows["signing.code_issued"]["summary"].startswith("действует до ")
    assert code["code"] not in str(rows["signing.code_issued"]["details"])  # код не пишется
    assert rows["loan.issued"]["summary"] == "SIGNED → ISSUED"
    assert rows["application.submitted"]["actor_name"] == "Ирина Соколова"
    assert rows["application.submitted"]["application_number"] == app["number"]
    assert rows["application.submitted"]["ip"] == "testclient"
    assert rows["loan.issued"]["ip"] is None  # система


def test_logins_are_logged_without_password(client: TestClient) -> None:
    auth_headers(client, "kovalev@demo.local")
    client.post(
        "/api/v1/auth/login", json={"email": "nobody@demo.local", "password": "wrong-password"}
    )

    rows = _audit(client, action=["auth.login", "auth.login_failed"])

    failed = next(r for r in rows if r["action"] == "auth.login_failed")
    assert (failed["actor_role"], failed["actor_id"], failed["actor_name"]) == (
        "client",
        None,
        "nobody@demo.local",
    )
    assert "wrong-password" not in str(failed)
    ok = next(r for r in rows if r["actor_name"] == "Андрей Ковалёв")
    assert (ok["action"], ok["summary"]) == ("auth.login", "kovalev@demo.local")


def test_documents_resubmit_and_download_are_logged(client: TestClient, storage: Path) -> None:
    app, headers = submit_demo(client, *MELNIKOVA)
    doc = client.post(
        f"/api/v1/applications/{app['id']}/documents",
        files={"file": ("декларация.pdf", PDF, "application/pdf")},
        data={"kind": "tax_return"},
        headers=headers,
    ).json()
    client.post(f"/api/v1/applications/{app['id']}/resubmit", headers=headers)
    client.get(f"/api/v1/documents/{doc['id']}", headers=auth_headers(client, UNDERWRITER))

    rows = _audit(client, application_id=app["id"])

    uploaded = next(r for r in rows if r["action"] == "document.uploaded")
    assert uploaded["summary"] == "декларация.pdf"
    assert uploaded["details"] == {"document_id": doc["id"], "kind": "tax_return", "size_bytes": 28}
    assert next(r for r in rows if r["action"] == "application.resubmitted")["summary"] == (
        "INFO_REQUESTED → SUBMITTED"
    )
    downloaded = next(r for r in rows if r["action"] == "document.downloaded")
    assert (downloaded["actor_role"], downloaded["actor_name"]) == ("underwriter", "Дмитрий Орлов")


def test_bank_actions_are_logged_once(client: TestClient) -> None:
    app, _ = submit_demo(client, *MIRAGE)
    bank = auth_headers(client, UNDERWRITER)
    for _ in range(2):  # повторное «взять в работу» ничего не меняет и в журнал не пишется
        client.post(f"/api/v1/bank/applications/{app['id']}/assign", headers=bank)
    client.post(
        f"/api/v1/bank/applications/{app['id']}/decision",
        json={"outcome": "approved", "rate": "22.00"},
        headers=bank,
    )

    rows = _audit(client, application_id=app["id"], actor_role="underwriter")

    assert [r["action"] for r in rows] == ["bank.decision", "bank.assigned"]
    decision = rows[0]
    assert decision["summary"] == "MANUAL_REVIEW → APPROVED"
    assert decision["details"]["outcome"] == "approved"


def test_cancel_is_logged_and_failed_action_is_not(client: TestClient) -> None:
    draft, headers = create_draft(client, *BAKERY)
    incomplete, _ = create_draft(client, "bakery@demo.local", {})
    client.post(f"/api/v1/applications/{incomplete['id']}/submit", headers=headers)  # 422
    client.post(f"/api/v1/applications/{draft['id']}/cancel", headers=headers)

    assert [a for a, _, _ in _trail(client, draft)] == [
        "application.created",
        "application.cancelled",
    ]
    assert [a for a, _, _ in _trail(client, incomplete)] == ["application.created"]


# ── Чтение журнала ──────────────────────────────────────────────────────────


def test_filters_and_pages(client: TestClient) -> None:
    bakery, _ = submit_demo(client, *BAKERY)
    submit_demo(client, *KOVALEV)

    systems = _audit(client, actor_role="system")
    page = _audit(client, limit=3)
    next_page = _audit(client, limit=3, before=page[-1]["created_at"])
    own = _audit(client, application_id=bakery["id"], action=["application.submitted"])

    assert systems and all(r["actor_role"] == "system" for r in systems)
    times = [r["created_at"] for r in page + next_page]
    assert times == sorted(times, reverse=True)  # свежие сверху
    assert {r["id"] for r in page}.isdisjoint({r["id"] for r in next_page})
    assert [r["application_id"] for r in own] == [bakery["id"]]


def test_audit_is_for_bank_staff(client: TestClient) -> None:
    assert len(_audit(client, UNDERWRITER)) >= 1
    client_headers = auth_headers(client, "bakery@demo.local")
    assert client.get("/api/v1/bank/audit", headers=client_headers).status_code == 403
    assert client.get("/api/v1/bank/audit").status_code == 401


# ── Сброс демо ──────────────────────────────────────────────────────────────


def test_reset_removes_applications_and_keeps_journal(
    client: TestClient, storage: Path, demo_mode: None
) -> None:
    app, headers = submit_demo(client, *MELNIKOVA)
    client.post(
        f"/api/v1/applications/{app['id']}/documents",
        files={"file": ("декларация.pdf", PDF, "application/pdf")},
        data={"kind": "tax_return"},
        headers=headers,
    )
    submit_demo(client, *BAKERY)
    assert any(storage.iterdir())

    response = _reset(client)

    assert response.status_code == 200, response.text
    assert response.json()["applications_deleted"] == 2
    assert client.get("/api/v1/applications", headers=headers).json() == []
    assert (
        client.get("/api/v1/feed", params={"kind": "event"}, headers=headers).json()["items"] == []
    )
    assert not any(storage.iterdir())  # файлы клиентов удалены
    assert (
        client.post(  # учётки и продукты на месте
            "/api/v1/auth/login", json={"email": "bakery@demo.local", "password": DEMO_PASSWORD}
        ).status_code
        == 200
    )
    rows = _audit(client)
    reset = next(r for r in rows if r["action"] == "demo.reset")
    assert (reset["actor_role"], reset["summary"]) == ("admin", "удалено заявок: 2")
    old = next(r for r in rows if r["application_id"] == app["id"])
    assert old["application_number"] == app["number"]  # журнал пережил сброс


def test_second_reset_is_safe(client: TestClient, demo_mode: None) -> None:
    submit_demo(client, *BAKERY)
    _reset(client)

    again = _reset(client)

    assert again.status_code == 200
    assert again.json()["applications_deleted"] == 0
    assert len([r for r in _audit(client) if r["action"] == "demo.reset"]) == 2


def test_reset_without_demo_mode_is_409(client: TestClient) -> None:
    submit_demo(client, *BAKERY)

    response = _reset(client)

    assert response.status_code == 409
    assert response.json()["code"] == "demo_mode_disabled"
    assert len(client.get("/api/v1/applications", headers=auth_headers(client)).json()) == 1


def test_reset_is_admin_only(client: TestClient, demo_mode: None) -> None:
    assert _reset(client, UNDERWRITER).status_code == 403
    assert _reset(client, "bakery@demo.local").status_code == 403
    assert client.post("/api/v1/admin/demo/reset").status_code == 401

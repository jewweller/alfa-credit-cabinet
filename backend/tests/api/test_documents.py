"""Документы и resubmit: сценарий Мельниковой и ограничения загрузки (план, разделы 4, 7, 9)."""

import hashlib
from pathlib import Path
from uuid import UUID

import pytest
from conftest import auth_headers
from demo_flows import BAKERY, MELNIKOVA, create_draft, rows, steps, submit_demo
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.db.models import DecisionRow, DocumentRow, InfoRequestRow
from app.schemas.documents import MAX_UPLOAD_BYTES
from app.storage import LocalStorage, get_storage

PDF = b"%PDF-1.7\n% demo declaration\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def storage(client: TestClient, tmp_path: Path) -> Path:
    client.app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)  # type: ignore[attr-defined]
    return tmp_path


@pytest.fixture
def melnikova(client: TestClient, storage: Path) -> tuple[dict, dict]:
    app, headers = submit_demo(client, *MELNIKOVA)
    assert app["status"] == "INFO_REQUESTED"
    return app, headers


def _upload(  # noqa: ANN202
    client: TestClient,
    app: dict,
    headers: dict,
    *,
    content: bytes = PDF,
    mime: str = "application/pdf",
    kind: str = "tax_return",
    filename: str = "декларация 2025.pdf",
    info_request_id: str | None = None,
):
    data = {"kind": kind}
    if info_request_id:
        data["info_request_id"] = info_request_id
    return client.post(
        f"/api/v1/applications/{app['id']}/documents",
        files={"file": (filename, content, mime)},
        data=data,
        headers=headers,
    )


def _resubmit(client: TestClient, app: dict, headers: dict):  # noqa: ANN202
    return client.post(f"/api/v1/applications/{app['id']}/resubmit", headers=headers)


# ── Сценарий Мельниковой ────────────────────────────────────────────────────


def test_melnikova_documents_then_manual_review(
    client: TestClient, engine: Engine, storage: Path, melnikova: tuple[dict, dict]
) -> None:
    app, headers = melnikova
    request_id = app["info_request"]["id"]

    uploaded = _upload(client, app, headers, info_request_id=request_id)
    assert uploaded.status_code == 201
    document = uploaded.json()
    assert (document["kind"], document["mime"], document["size_bytes"]) == (
        "tax_return", "application/pdf", len(PDF),
    )  # fmt: skip
    assert document["filename"] == "декларация 2025.pdf"
    assert document["info_request_id"] == request_id

    response = _resubmit(client, app, headers)

    assert response.status_code == 200
    body = response.json()
    # План, раздел 7: документ загружен → R4 → MANUAL_REVIEW (решает специалист).
    assert body["status"] == "MANUAL_REVIEW"
    assert body["decision"]["outcome"] == "manual_review"
    assert body["info_request"] is None
    assert [d["id"] for d in body["documents"]] == [document["id"]]
    assert steps(client, app, headers)[-5:] == [
        ("SCORING", "INFO_REQUESTED", "system"),
        ("INFO_REQUESTED", "SUBMITTED", "client"),
        ("SUBMITTED", "ENRICHMENT", "system"),
        ("ENRICHMENT", "SCORING", "system"),
        ("SCORING", "MANUAL_REVIEW", "system"),
    ]
    decisions = sorted(rows(engine, DecisionRow, app["id"]), key=lambda d: d.created_at)
    assert [d.reason_code for d in decisions] == [
        "R4_REVENUE_PROOF_REQUIRED",
        "R4_REVENUE_MISMATCH_REVIEW",
    ]
    [request] = rows(engine, InfoRequestRow, app["id"])
    assert request.status == "answered"
    [stored] = rows(engine, DocumentRow, app["id"])
    assert stored.sha256 == hashlib.sha256(PDF).hexdigest()
    assert (storage / stored.storage_path).read_bytes() == PDF  # на диске — под UUID


def test_resubmit_without_required_document_is_422(
    client: TestClient, melnikova: tuple[dict, dict]
) -> None:
    app, headers = melnikova

    response = _resubmit(client, app, headers)

    assert response.status_code == 422
    assert response.json()["code"] == "documents_required"
    assert "Декларация или выписка" in response.json()["message"]


def test_document_of_other_kind_does_not_close_required_item(
    client: TestClient, melnikova: tuple[dict, dict]
) -> None:
    # Пункт запроса — tax_return (вопрос K4: «декларация или выписка» → один вид в контракте).
    app, headers = melnikova
    _upload(client, app, headers, kind="bank_statement")

    assert _resubmit(client, app, headers).status_code == 422


def test_second_resubmit_is_invalid_transition(
    client: TestClient, melnikova: tuple[dict, dict]
) -> None:
    app, headers = melnikova
    _upload(client, app, headers)
    _resubmit(client, app, headers)

    again = _resubmit(client, app, headers)

    assert again.status_code == 409
    assert again.json()["code"] == "invalid_transition"


def test_resubmit_outside_info_requested_is_invalid_transition(
    client: TestClient, storage: Path
) -> None:
    app, headers = submit_demo(client, *BAKERY)

    assert _resubmit(client, app, headers).status_code == 409


# ── Ограничения загрузки ────────────────────────────────────────────────────


def test_upload_only_while_documents_requested(client: TestClient, storage: Path) -> None:
    draft, headers = create_draft(client, *BAKERY)
    approved, _ = submit_demo(client, *BAKERY)

    for app in (draft, approved):
        response = _upload(client, app, headers)
        assert response.status_code == 409
        assert response.json()["code"] == "conflict"


def test_file_larger_than_limit_is_413(client: TestClient, melnikova: tuple[dict, dict]) -> None:
    app, headers = melnikova

    response = _upload(client, app, headers, content=PDF + b"0" * MAX_UPLOAD_BYTES)

    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


def test_file_of_exactly_the_limit_is_accepted(
    client: TestClient, melnikova: tuple[dict, dict]
) -> None:
    app, headers = melnikova
    content = PDF + b"0" * (MAX_UPLOAD_BYTES - len(PDF))

    assert _upload(client, app, headers, content=content).status_code == 201


@pytest.mark.parametrize(
    ("content", "mime"),
    [(b"hello", "text/plain"), (PNG, "application/pdf"), (PDF, "image/png")],
    ids=["text", "png-named-pdf", "pdf-named-png"],
)
def test_wrong_type_is_415(
    client: TestClient, melnikova: tuple[dict, dict], content: bytes, mime: str
) -> None:
    app, headers = melnikova

    response = _upload(client, app, headers, content=content, mime=mime)

    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_media_type"


def test_png_is_accepted(client: TestClient, melnikova: tuple[dict, dict]) -> None:
    app, headers = melnikova

    response = _upload(client, app, headers, content=PNG, mime="image/png", filename="scan.png")

    assert response.status_code == 201


def test_empty_file_is_422(client: TestClient, melnikova: tuple[dict, dict]) -> None:
    app, headers = melnikova

    response = _upload(client, app, headers, content=b"")

    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "message": "Файл пустой",
        "field": "file",
    }


def test_unknown_kind_is_422(client: TestClient, melnikova: tuple[dict, dict]) -> None:
    app, headers = melnikova

    response = _upload(client, app, headers, kind="passport")

    assert response.status_code == 422
    assert response.json()["field"] == "kind"


def test_info_request_of_other_application_is_422(
    client: TestClient, melnikova: tuple[dict, dict]
) -> None:
    app, headers = melnikova

    response = _upload(client, app, headers, info_request_id=str(UUID(int=5)))

    assert response.status_code == 422
    assert response.json()["field"] == "info_request_id"


def test_path_in_filename_is_dropped(
    client: TestClient, engine: Engine, melnikova: tuple[dict, dict]
) -> None:
    app, headers = melnikova

    response = _upload(client, app, headers, filename="../../etc/passwd.pdf")

    assert response.json()["filename"] == "passwd.pdf"
    [stored] = rows(engine, DocumentRow, app["id"])
    assert stored.storage_path.isalnum() and len(stored.storage_path) == 32


def test_upload_access(client: TestClient, melnikova: tuple[dict, dict]) -> None:
    app, _ = melnikova

    assert _upload(client, app, auth_headers(client, "bakery@demo.local")).status_code == 404
    assert _upload(client, app, auth_headers(client, "underwriter@demo.local")).status_code == 403
    assert _upload(client, app, {}).status_code == 401


# ── Скачивание ──────────────────────────────────────────────────────────────


def test_download_own_document(client: TestClient, melnikova: tuple[dict, dict]) -> None:
    app, headers = melnikova
    document = _upload(client, app, headers).json()

    response = client.get(f"/api/v1/documents/{document['id']}", headers=headers)

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert "filename*=UTF-8''" in response.headers["content-disposition"]


def test_download_access(client: TestClient, melnikova: tuple[dict, dict]) -> None:
    app, headers = melnikova
    path = f"/api/v1/documents/{_upload(client, app, headers).json()['id']}"

    other = client.get(path, headers=auth_headers(client, "bakery@demo.local"))
    assert other.status_code == 403  # контракт: «файл из чужой заявки» — 403
    assert (
        client.get(path, headers=auth_headers(client, "underwriter@demo.local")).status_code == 200
    )
    assert client.get(path).status_code == 401
    assert client.get(f"/api/v1/documents/{UUID(int=9)}", headers=headers).status_code == 404

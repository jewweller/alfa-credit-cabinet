"""Готовность API: база, миграции, файлы источников и новостей."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_session
from app.services.readiness import expected_revision

PATHS = ["/ready", "/api/v1/ready"]


def _stamp(engine: Engine) -> None:
    """Как после `alembic upgrade head`: в тестовой БД таблицы созданы без Alembic."""
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        connection.execute(
            text("INSERT INTO alembic_version VALUES (:v)"), {"v": expected_revision()}
        )


def test_head_revision_is_latest_migration() -> None:
    assert expected_revision() == "0007"


@pytest.mark.parametrize("path", PATHS)
def test_ready_when_everything_is_in_place(client: TestClient, engine: Engine, path: str) -> None:
    _stamp(engine)

    response = client.get(path)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "migrations": "ok", "fixtures": "ok", "news": "ok"},
    }


@pytest.mark.parametrize("path", PATHS)
def test_not_ready_without_migrations(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 503
    assert response.json()["code"] == "upstream_unavailable"
    assert response.json()["message"] == "API не готов: migrations"


def test_not_ready_on_old_migration(client: TestClient, engine: Engine) -> None:
    _stamp(engine)
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = '0006'"))

    assert client.get("/ready").json()["message"] == "API не готов: migrations"


def test_not_ready_without_news(
    client: TestClient, engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stamp(engine)
    monkeypatch.setattr(get_settings(), "seed_dir", tmp_path)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["message"] == "API не готов: news"


def test_not_ready_when_database_is_down(client: TestClient, tmp_path: Path) -> None:
    broken = create_engine(f"sqlite+pysqlite:///{tmp_path}/missing/dir/db.sqlite")

    def _session() -> Iterator[Session]:
        with Session(broken) as session:
            yield session

    client.app.dependency_overrides[get_session] = _session  # type: ignore[attr-defined]

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["message"] == "API не готов: database, migrations"


def test_health_does_not_depend_on_database(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}

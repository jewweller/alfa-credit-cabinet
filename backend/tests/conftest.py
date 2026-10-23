"""Общие фикстуры: API поверх SQLite в памяти с загруженными демо-данными из seed/."""

import os

# До импорта приложения: настройки кешируются при первом обращении.
os.environ.setdefault("JWT_SECRET", "pytest-only-secret-key-0123456789abcdef")
os.environ.setdefault("BCRYPT_ROUNDS", "4")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed_demo_data  # noqa: E402

DEMO_PASSWORD = "Demo2026!"


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_demo_data(session, get_settings().seed_dir)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine: Engine) -> TestClient:
    app = create_app()

    def _session() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = _session
    return TestClient(app)


def auth_headers(client: TestClient, email: str = "bakery@demo.local") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

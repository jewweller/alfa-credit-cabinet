"""Готовность API (план, раздел 10: `/health` и `/ready`).

`/health` — процесс жив. `/ready` — API может обслуживать запросы: база отвечает, миграции
применены до последней версии, на месте файлы, без которых не работают заявки и лента
(ответы источников и новости). Healthcheck контейнера в docker-compose смотрит на `/ready`.
"""

from functools import lru_cache
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import get_settings
from app.schemas.common import ErrorCode
from app.schemas.system import ReadyResponse

# backend/app/services/readiness.py → backend/alembic; в образе: /app/alembic.
_ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"


@lru_cache
def expected_revision() -> str | None:
    return ScriptDirectory(str(_ALEMBIC_DIR)).get_current_head()


def _database(session: Session) -> tuple[bool, bool]:
    """(база отвечает, миграции до последней версии)."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        session.rollback()
        return False, False
    try:
        current = session.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError:  # таблицы нет — миграции не применялись
        session.rollback()
        return True, False
    return True, current == expected_revision()


def check(session: Session) -> ReadyResponse:
    settings = get_settings()
    database, migrations = _database(session)
    checks = {
        "database": database,
        "migrations": migrations,
        "fixtures": settings.fixtures_dir.is_dir(),
        "news": (settings.seed_dir / "news.json").is_file(),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise ApiError(503, ErrorCode.UPSTREAM_UNAVAILABLE, f"API не готов: {', '.join(failed)}")
    return ReadyResponse(status="ready", checks=dict.fromkeys(checks, "ok"))

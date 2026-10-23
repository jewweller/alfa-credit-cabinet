"""Окружение Alembic: подключение из DATABASE_URL, метаданные — из app.db.models."""

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings
from app.db.models import Base

target_metadata = Base.metadata


def _url() -> str:
    # Тесты передают URL напрямую через config.attributes, приложение — через env.
    url = context.config.attributes.get("url") or get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL не задан")
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

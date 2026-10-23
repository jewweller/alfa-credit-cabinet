from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Base, Company, Product, User
from app.seed import seed_demo_data

BACKEND = Path(__file__).resolve().parents[2]


def test_seed_is_idempotent(engine: Engine) -> None:
    with Session(engine) as session:
        before = session.scalar(select(User.password_hash).where(User.email == "bakery@demo.local"))
        counts = seed_demo_data(session, get_settings().seed_dir)  # второй запуск
        after = session.scalar(select(User.password_hash).where(User.email == "bakery@demo.local"))

        assert counts == {"companies": 7, "products": 3, "users": 9}
        assert session.scalar(select(func.count()).select_from(User)) == 9
        assert session.scalar(select(func.count()).select_from(Company)) == 7
        assert session.scalar(select(func.count()).select_from(Product)) == 3
        assert before == after  # хэш не пересчитан


def test_migrations_match_models(tmp_path: Path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'migrated.db'}"
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["url"] = url

    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []

    command.downgrade(config, "base")

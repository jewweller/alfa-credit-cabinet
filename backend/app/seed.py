"""Загрузка демо-данных из seed/*.json (план, раздел 9). Идемпотентно: повтор не создаёт дублей.

Запуск: `python -m app.seed`. Выполняется только при SEED_DEMO_DATA=true.
"""

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Company, Product, User
from app.db.session import get_engine
from app.security import hash_password, verify_password


def _load(seed_dir: Path, name: str) -> list[dict]:
    return json.loads((seed_dir / name).read_text(encoding="utf-8"))


def seed_demo_data(session: Session, seed_dir: Path) -> dict[str, int]:
    """Создаёт или обновляет записи по id. Возвращает число записей каждого типа."""
    companies = _load(seed_dir, "companies.json")
    for row in companies:
        registered_at = date.fromisoformat(row["registered_at"])
        session.merge(Company(**{**row, "id": UUID(row["id"]), "registered_at": registered_at}))

    products = _load(seed_dir, "products.json")
    for row in products:
        session.merge(
            Product(
                **{
                    **row,
                    "id": UUID(row["id"]),
                    "min_amount": Decimal(row["min_amount"]),
                    "max_amount": Decimal(row["max_amount"]),
                    "base_rate": Decimal(row["base_rate"]),
                }
            )
        )
    session.flush()

    users = _load(seed_dir, "users.json")
    for row in users:
        user_id = UUID(row["id"])
        existing = session.get(User, user_id)
        # Не пересчитываем хэш на каждом старте, если пароль не менялся.
        if existing is not None and verify_password(row["password"], existing.password_hash):
            password_hash = existing.password_hash
        else:
            password_hash = hash_password(row["password"])
        session.merge(
            User(
                id=user_id,
                email=row["email"],
                password_hash=password_hash,
                role=row["role"],
                full_name=row["full_name"],
                company_id=UUID(row["company_id"]) if row["company_id"] else None,
            )
        )
    session.commit()
    return {"companies": len(companies), "products": len(products), "users": len(users)}


def main() -> int:
    settings = get_settings()
    if not settings.seed_demo_data:
        print("seed: SEED_DEMO_DATA не включён — демо-данные не загружаются")
        return 0
    with Session(get_engine()) as session:
        counts = seed_demo_data(session, settings.seed_dir)
    print(f"seed: загружено из {settings.seed_dir}: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

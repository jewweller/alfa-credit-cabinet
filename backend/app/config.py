"""Конфигурация приложения из переменных окружения (секреты только из env, см. план, раздел 9)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py → корень репозитория; в контейнере /app/app/config.py → «/».
_DEFAULT_SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "test", "demo", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # postgresql+psycopg://user:password@host:5432/db. Без него API работает только с /health.
    database_url: str | None = None
    # Подпись JWT (HS256). Не короче 32 символов, иначе HMAC-ключ считается слабым.
    jwt_secret: SecretStr | None = Field(default=None, min_length=32)
    jwt_ttl_minutes: int = Field(default=480, ge=1)
    # Стоимость bcrypt. 12 — для стенда; в тестах снижается, чтобы хэширование не тормозило.
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)

    # Демо-данные (учётки, компании, продукты) загружаются только при явном включении.
    seed_demo_data: bool = False
    seed_dir: Path = _DEFAULT_SEED_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()

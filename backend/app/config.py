"""Конфигурация приложения из переменных окружения (секреты только из env, см. план, раздел 9)."""

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py → корень репозитория; в контейнере /app/app/config.py → «/».
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SEED_DIR = _REPO_ROOT / "seed"
_DEFAULT_FIXTURES_DIR = _REPO_ROOT / "mocks" / "fixtures"


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
    # Ответы ЕГРЮЛ / ЕГРИП / ФНС / БКИ, пока нет HTTP-сервиса mocks.
    fixtures_dir: Path = _DEFAULT_FIXTURES_DIR
    # Файлы клиентов. В Docker — volume `uploads`; по умолчанию — вне репозитория.
    uploads_dir: Path = Path(tempfile.gettempdir()) / "alfa-credit-uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()

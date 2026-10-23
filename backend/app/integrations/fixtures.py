"""Источник данных из mocks/fixtures/*.json — временная замена HTTP-сервиса mocks.

Если ИНН в фикстурах нет: реестр отвечает «не найдено» (как 404 мока), ФНС и БКИ —
«недоступен» (как исчерпанные повторы). Запись `{"http_status": 503}` — источник отвечает
ошибкой сервера: результат как после всех повторов из config.yaml (integrations.retries).
Дальше это обрабатывают правила R1 и R3.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.integrations.base import SOURCES, FetchResult
from app.scoring.config import load_config
from app.scoring.inputs import SourceState

_REGISTRIES = {"egrul", "egrip"}


class FixtureSourceClient:
    def __init__(self, fixtures_dir: Path, retries: int) -> None:
        self._attempts = 1 + retries
        self._data: dict[str, dict[str, Any]] = {}
        for source in SOURCES:
            raw = json.loads((fixtures_dir / f"{source}.json").read_text(encoding="utf-8"))
            self._data[source] = {
                inn: entry for inn, entry in raw.items() if not inn.startswith("_")
            }

    def fetch(self, source: str, inn: str) -> FetchResult:
        entry = self._data[source].get(inn)
        if entry is not None and "http_status" in entry:
            status = int(entry["http_status"])
            if status == 404 and source in _REGISTRIES:
                return FetchResult(source, SourceState.NOT_FOUND, error="компания не найдена")
            # 5xx повторяется до исчерпания попыток, остальные ошибки — без повторов.
            attempts = self._attempts if status >= 500 else 1
            return FetchResult(
                source, SourceState.UNAVAILABLE, attempts=attempts, error=f"HTTP {status}"
            )
        if entry is not None:
            return FetchResult(source, SourceState.OK, entry["response"])
        if source in _REGISTRIES:
            return FetchResult(source, SourceState.NOT_FOUND, error="компания не найдена")
        return FetchResult(source, SourceState.UNAVAILABLE, error="нет данных в фикстурах")


@lru_cache
def get_source_client() -> FixtureSourceClient:
    return FixtureSourceClient(get_settings().fixtures_dir, load_config().integrations.retries)

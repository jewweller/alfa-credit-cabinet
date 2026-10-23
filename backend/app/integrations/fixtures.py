"""Источник данных из mocks/fixtures/*.json — временная замена HTTP-сервиса mocks.

Если ИНН в фикстурах нет: реестр отвечает «не найдено» (как 404 мока), ФНС и БКИ —
«недоступен» (как исчерпанные повторы). Дальше это обрабатывают правила R1 и R3.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.integrations.base import SOURCES, FetchResult
from app.scoring.inputs import SourceState

_REGISTRIES = {"egrul", "egrip"}


class FixtureSourceClient:
    def __init__(self, fixtures_dir: Path) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        for source in SOURCES:
            raw = json.loads((fixtures_dir / f"{source}.json").read_text(encoding="utf-8"))
            self._data[source] = {
                inn: entry for inn, entry in raw.items() if not inn.startswith("_")
            }

    def fetch(self, source: str, inn: str) -> FetchResult:
        entry = self._data[source].get(inn)
        if entry is not None:
            return FetchResult(source, SourceState.OK, entry["response"])
        if source in _REGISTRIES:
            return FetchResult(source, SourceState.NOT_FOUND, error="компания не найдена")
        return FetchResult(source, SourceState.UNAVAILABLE, error="нет данных в фикстурах")


@lru_cache
def get_source_client() -> FixtureSourceClient:
    return FixtureSourceClient(get_settings().fixtures_dir)

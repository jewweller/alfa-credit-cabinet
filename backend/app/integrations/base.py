"""Интерфейс внешних источников (ЕГРЮЛ, ЕГРИП, ФНС «Прозрачный бизнес», БКИ).

Реализация отдаёт сырой ответ по контракту мока (план, раздел 8) и итог обращения.
Сейчас — фикстуры в процессе API (fixtures.py); позже — HTTP-адаптер к сервису mocks
с таймаутами и повторами из config.yaml. Скоринг и решение от реализации не зависят.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from app.scoring.inputs import SourceState

SOURCES = ("egrul", "egrip", "fns_tb", "bki")


@dataclass(frozen=True)
class FetchResult:
    source: str
    state: SourceState
    payload: dict[str, Any] | None = None
    attempts: int = 1
    error: str | None = None


class SourceClient(Protocol):
    def fetch(self, source: str, inn: str) -> FetchResult:
        """Ответ источника по ИНН. Не бросает исключений из-за сбоев источника."""
        ...

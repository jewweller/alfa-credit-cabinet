"""Служебные ответы: живость и готовность API (план, раздел 10)."""

from typing import Literal

from pydantic import BaseModel, Field


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    checks: dict[str, Literal["ok"]] = Field(
        description="Что проверено: база, миграции, файлы ответов источников и новостей.",
        examples=[{"database": "ok", "migrations": "ok", "fixtures": "ok", "news": "ok"}],
    )

"""Обмен бэкенда с ML-ранжированием (docs/ml-ranking.md). Это не HTTP API: в OpenAPI не попадает.

ML только меняет порядок кандидатов, которые уже отобрал бэкенд. Добавить, убрать или
изменить кандидата модель не может; кредитное решение принимают правила R1–R10 и специалист.
Ответ, который не проходит эти схемы или `is_permutation`, бэкенд отбрасывает и оставляет
порядок по правилам.
"""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.state_machine import ApplicationStatus
from app.schemas.companies import CompanyKind, CompanySegment
from app.schemas.feed import FeedReason, FeedReasonCode, NewsItem
from app.schemas.products import LoanPurpose, ProductRecommendation, ProductRecommendRequest


class RankerApplication(BaseModel):
    """Заявка клиента — без сумм анкеты: в ленте и подборе они не нужны."""

    status: ApplicationStatus
    product_code: str | None = Field(examples=["EXPRESS_WC"])
    purpose: LoanPurpose | None


class RankerProfile(BaseModel):
    """Профиль клиента без ИНН и названия: модели они не нужны.

    Данные БКИ сюда не входят: согласие на запрос в БКИ клиент даёт только для решения
    по своей заявке, не для подбора продуктов и новостей.
    """

    kind: CompanyKind
    okved_main: str = Field(examples=["10.71"])
    region: str = Field(examples=["Москва"])
    segment: CompanySegment
    registered_at: date
    revenue: dict[str, int] = Field(
        description="Выручка по годам из ФНС «Прозрачный бизнес», рублей; может быть пустой.",
        examples=[{"2024": 21428571, "2025": 24000000}],
    )
    applications: list[RankerApplication] = Field(description="Заявки клиента, кроме CANCELLED.")


def _unique(ids: Iterable[UUID]) -> bool:
    ids = list(ids)
    return len(ids) == len(set(ids))


def is_permutation(ranked: Iterable[UUID], candidates: Iterable[UUID]) -> bool:
    """В ответе ровно те же кандидаты, каждый один раз."""
    ranked, candidates = list(ranked), list(candidates)
    return len(ranked) == len(candidates) and set(ranked) == set(candidates)


# ── Лента (экраны C2, C8) ─────────────────────────────────────────────────────


class FeedRankCandidate(NewsItem):
    """Новость, которую можно показать клиенту, с весом и совпадениями по правилам."""

    rule_score: float = Field(description="Вес по формуле плана — базовая линия и признак.")
    matched: list[FeedReasonCode] = Field(description="Совпавшие теги; `general` — тегов нет.")


class FeedRankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    now: datetime = Field(description="Текущее время — от него считается свежесть.")
    profile: RankerProfile
    candidates: list[FeedRankCandidate] = Field(min_length=1)


class FeedRankItem(BaseModel):
    id: UUID
    score: float = Field(ge=0, le=1, description="0…1, больше — выше в списке.")
    reasons: list[FeedReason] = Field(
        default_factory=list,
        max_length=2,
        description="Свои «Почему вы это видите»; пусто — бэкенд покажет причины по правилам.",
    )


class FeedRankResponse(BaseModel):
    model_version: str = Field(examples=["feed-ranker-0.1.0"])
    ranking: list[FeedRankItem] = Field(description="Все кандидаты, лучший первым.")

    @model_validator(mode="after")
    def _ids_unique(self) -> Self:
        if not _unique(item.id for item in self.ranking):
            raise ValueError("ranking: id повторяются")
        return self


# ── Подбор продукта (экран C3) ────────────────────────────────────────────────


class ProductRankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: ProductRecommendRequest
    profile: RankerProfile
    candidates: list[ProductRecommendation] = Field(min_length=1)


class ProductRankItem(BaseModel):
    product_id: UUID
    score: float = Field(ge=0, le=1, description="0…1, больше — выше в списке.")
    reasons: list[Annotated[str, Field(max_length=120)]] = Field(
        default_factory=list,
        max_length=2,
        description="Короткие фразы для клиента. В интерфейсе пока не показаны.",
    )


class ProductRankResponse(BaseModel):
    model_version: str = Field(examples=["product-ranker-0.1.0"])
    ranking: list[ProductRankItem]

    @model_validator(mode="after")
    def _ids_unique(self) -> Self:
        if not _unique(item.product_id for item in self.ranking):
            raise ValueError("ranking: product_id повторяются")
        return self

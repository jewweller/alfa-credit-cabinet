"""Персональная лента клиента: события по заявкам и новости по профилю (план, раздел 11 — C2, C8).

События — уведомления о смене статуса заявки (вместо email/SMS, которых нет по условиям кейса).
Новости — синтетические тексты из `seed/news.json`; у каждой есть причина показа.
"""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.state_machine import ApplicationStatus
from app.schemas.common import DescribedStrEnum
from app.schemas.companies import CompanySegment


class FeedItemKind(StrEnum):
    EVENT = "event"
    NEWS = "news"


class FeedReasonCode(DescribedStrEnum):
    """Какой тег новости совпал с профилем клиента."""

    OKVED = "okved"
    SEGMENT = "segment"
    PRODUCT = "product"
    STATUS = "status"
    GENERAL = "general"

    @classmethod
    def value_descriptions(cls) -> Mapping[str, str]:
        return FEED_REASON_DESCRIPTIONS


FEED_REASON_DESCRIPTIONS: Mapping[str, str] = {
    FeedReasonCode.OKVED: "группа ОКВЭД компании, например «Ваш ОКВЭД 10.71 — производство хлеба»",
    FeedReasonCode.SEGMENT: "сегмент: микро или малый бизнес",
    FeedReasonCode.PRODUCT: "продукт в одной из заявок клиента",
    FeedReasonCode.STATUS: "текущий статус одной из заявок клиента",
    FeedReasonCode.GENERAL: "ни один тег не совпал — новость для всех клиентов",
}


class FeedReason(BaseModel):
    """Строка «Почему вы это видите»."""

    code: FeedReasonCode
    text: str = Field(max_length=120, examples=["Ваш ОКВЭД 10.71 — производство хлеба"])


class FeedRankingMethod(DescribedStrEnum):
    """Чем отсортированы новости."""

    RULES = "rules"
    ML = "ml"

    @classmethod
    def value_descriptions(cls) -> Mapping[str, str]:
        return {
            cls.RULES: "формула весов плана: 3·ОКВЭД + 2·сегмент + 2·продукт + 3·статус + свежесть",
            cls.ML: "модель ML-команды; при ошибке или таймауте — откат на rules",
        }


class FeedRanking(BaseModel):
    method: FeedRankingMethod
    model_version: str = Field(examples=["feed-rules-1.0"])


class FeedItem(BaseModel):
    """Событие по заявке или новость."""

    id: UUID
    kind: FeedItemKind
    title: str = Field(examples=["Заявка №1051 одобрена"])
    body: str
    created_at: datetime = Field(
        description="Событие — когда произошло; новость — дата публикации."
    )
    read: bool = Field(
        description="Прочитано ли событие. У новостей всегда true: отметка только для событий."
    )
    application_id: UUID | None = Field(description="Заявка события; у новостей null.")
    application_number: str | None = Field(examples=["1051"], description="Номер заявки события.")
    status: ApplicationStatus | None = Field(
        description="Статус, в который перешла заявка; у новостей null."
    )
    reasons: list[FeedReason] = Field(
        description="«Почему вы это видите», самое сильное совпадение первым. У событий пусто."
    )
    score: float | None = Field(
        description="Вес новости в выбранном методе (`ranking.method`); у событий null."
    )


class FeedResponse(BaseModel):
    """Лента: сверху события (свежие первыми), ниже новости по убыванию `score`."""

    items: list[FeedItem]
    ranking: FeedRanking


# ── Синтетические новости (seed/news.json) ───────────────────────────────────


class NewsTopic(DescribedStrEnum):
    PRODUCT = "product"
    INDUSTRY = "industry"
    STEP = "step"
    SUPPORT = "support"

    @classmethod
    def value_descriptions(cls) -> Mapping[str, str]:
        return {
            cls.PRODUCT: "условия наших продуктов",
            cls.INDUSTRY: "отраслевая заметка",
            cls.STEP: "подсказка по текущему шагу заявки",
            cls.SUPPORT: "советы и меры поддержки МСП (синтетические)",
        }


class NewsTags(BaseModel):
    """Теги новости. Пустой список — тег не задан и не влияет на вес."""

    okved: list[str] = Field(
        default_factory=list,
        description="Группы ОКВЭД — первые две цифры кода, например `10`.",
        examples=[["10"]],
    )
    segment: list[CompanySegment] = Field(default_factory=list)
    product: list[str] = Field(
        default_factory=list, description="Коды продуктов.", examples=[["EXPRESS_WC"]]
    )
    status: list[ApplicationStatus] = Field(default_factory=list)


class NewsItem(BaseModel):
    """Новость из `seed/news.json` (таблица `news_items`)."""

    id: UUID
    title: str = Field(max_length=120)
    body: str
    topic: NewsTopic
    tags: NewsTags
    published_at: datetime

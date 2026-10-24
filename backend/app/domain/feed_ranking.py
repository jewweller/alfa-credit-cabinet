"""Ранжирование новостей ленты правилами (план, раздел 11, «Как работает персональная лента»).

вес = 3·[ОКВЭД] + 2·[сегмент] + 2·[продукт] + 3·[статус] + свежесть, свежесть = max(0, 1 − дней/30).

Уточнения к плану, чтобы у каждой показанной новости была честная причина:
- теги ОКВЭД и статуса — фильтры: отраслевая заметка не для своей отрасли и подсказка
  не к своему шагу не показываются вовсе, а не просто получают меньший вес;
- новость с тегами показывается, только если совпал хотя бы один; новость без тегов — для всех.
Это же базовая линия и запасной вариант для ML-ранжирования.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from app.domain.state_machine import ApplicationStatus
from app.schemas.companies import CompanySegment
from app.schemas.feed import FeedReason, FeedReasonCode, NewsItem

MODEL_VERSION = "feed-rules-1.0"
NEWS_LIMIT = 10
FRESHNESS_DAYS = 30

WEIGHTS: Mapping[FeedReasonCode, int] = {
    FeedReasonCode.OKVED: 3,
    FeedReasonCode.STATUS: 3,
    FeedReasonCode.PRODUCT: 2,
    FeedReasonCode.SEGMENT: 2,
}

# Названия кодов ОКВЭД демо-клиентов (seed/companies.json) — для строки «Почему вы это видите».
OKVED_NAMES: Mapping[str, str] = {
    "10.71": "производство хлеба и мучных изделий",
    "41.20": "строительство зданий",
    "46.90": "оптовая торговля",
    "47.11": "розничная торговля продуктами",
    "56.10": "рестораны и кафе",
    "62.01": "разработка программ",
    "96.02": "парикмахерские и салоны красоты",
}

SEGMENT_TEXT: Mapping[CompanySegment, str] = {
    CompanySegment.MICRO: "Подобрано для микробизнеса",
    CompanySegment.SMALL: "Подобрано для малого бизнеса",
}

S = ApplicationStatus
STATUS_TEXT: Mapping[ApplicationStatus, str] = {
    S.DRAFT: "У вас есть черновик заявки",
    S.SUBMITTED: "Ваша заявка на проверке",
    S.ENRICHMENT: "Ваша заявка на проверке",
    S.SCORING: "Ваша заявка на проверке",
    S.MANUAL_REVIEW: "Вашу заявку рассматривает специалист",
    S.INFO_REQUESTED: "Ваша заявка ждёт документы",
    S.APPROVED: "Ваша заявка одобрена",
    S.COUNTER_OFFER: "Банк предложил вам другие условия",
    S.REJECTED: "По вашей заявке отказ",
    S.SIGNING: "Вы подписываете договор",
    S.SIGNED: "Договор подписан",
    S.ISSUED: "Кредит выдан",
    S.DECLINED_BY_CLIENT: "Вы отказались от предложения",
}

GENERAL_TEXT = "Полезно всем клиентам"


def okved_group(code: str) -> str:
    """Группа ОКВЭД — первые две цифры: `10.71` → `10`."""
    return code.split(".", 1)[0][:2]


@dataclass(frozen=True)
class FeedProfile:
    """Что о клиенте нужно ленте. Отменённые заявки (CANCELLED) сюда не попадают."""

    okved_main: str
    segment: CompanySegment
    products: Mapping[str, str]  # код продукта → название, из заявок клиента
    statuses: frozenset[ApplicationStatus]


@dataclass(frozen=True)
class RankedNews:
    news: NewsItem
    score: float
    reasons: list[FeedReason]


def _matches(news: NewsItem, profile: FeedProfile) -> list[FeedReason] | None:
    """Совпавшие теги, самое сильное первым; None — новость клиенту не показывается."""
    tags = news.tags
    reasons: list[FeedReason] = []

    if tags.okved:
        if okved_group(profile.okved_main) not in tags.okved:
            return None
        name = OKVED_NAMES.get(profile.okved_main)
        text = f"Ваш ОКВЭД {profile.okved_main}" + (f" — {name}" if name else "")
        reasons.append(FeedReason(code=FeedReasonCode.OKVED, text=text))

    if tags.status:
        status = next((s for s in tags.status if s in profile.statuses), None)
        if status is None:
            return None
        reasons.append(FeedReason(code=FeedReasonCode.STATUS, text=STATUS_TEXT[status]))

    product = next((p for p in tags.product if p in profile.products), None)
    if product is not None:
        text = f"У вас заявка на «{profile.products[product]}»"
        reasons.append(FeedReason(code=FeedReasonCode.PRODUCT, text=text))

    if profile.segment in tags.segment:
        reasons.append(FeedReason(code=FeedReasonCode.SEGMENT, text=SEGMENT_TEXT[profile.segment]))

    if not reasons and (tags.product or tags.segment):
        return None
    return reasons


def freshness(published_at: datetime, now: datetime) -> float:
    days = max(0.0, (now - published_at).total_seconds() / 86400)
    return max(0.0, 1 - days / FRESHNESS_DAYS)


def eligible_news(
    news: Iterable[NewsItem], profile: FeedProfile, now: datetime
) -> list[RankedNews]:
    """Все новости, которые можно показать клиенту, с весом по правилам; порядок не задан."""
    result = []
    for item in news:
        reasons = _matches(item, profile)
        if reasons is None:
            continue
        score = sum(WEIGHTS[r.code] for r in reasons) + freshness(item.published_at, now)
        if not reasons:
            reasons = [FeedReason(code=FeedReasonCode.GENERAL, text=GENERAL_TEXT)]
        result.append(RankedNews(news=item, score=round(score, 2), reasons=reasons))
    return result


def rank_news(
    news: Iterable[NewsItem], profile: FeedProfile, now: datetime, limit: int = NEWS_LIMIT
) -> list[RankedNews]:
    """Топ новостей по весу; при равном весе — свежие первыми."""
    ranked = sorted(
        eligible_news(news, profile, now),
        key=lambda r: (-r.score, -r.news.published_at.timestamp(), str(r.news.id)),
    )
    return ranked[:limit]

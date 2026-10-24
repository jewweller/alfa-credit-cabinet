"""Персональная лента клиента: события по заявкам и новости по профилю (план, раздел 11).

События пишет `services.status.notify` при каждой смене статуса. Новости — `seed/news.json`,
вес и причины показа считает `domain.feed_ranking` (та же формула, что в моках фронта).

Временные решения backend (L1–L3, docs/analyst-questions.md, раздел 8) — аналитиком не
подтверждены:
  * события видны всем пользователям компании заявки — как в моках (один пользователь на
    компанию, план, раздел 2);
  * новости читаются из `seed/news.json` при первом запросе, отдельной таблицы нет;
  * сортировка только правилами (`ranking.method = rules`): модель ML пока не подключена.
"""

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import get_settings
from app.db.models import Application, FeedEventRow, User
from app.domain.feed_ranking import MODEL_VERSION, FeedProfile, rank_news
from app.domain.state_machine import ApplicationStatus
from app.schemas.common import ErrorCode
from app.schemas.companies import CompanySegment
from app.schemas.feed import (
    FeedItem,
    FeedItemKind,
    FeedRanking,
    FeedRankingMethod,
    FeedResponse,
    NewsItem,
)


@lru_cache
def _news(path: Path) -> tuple[NewsItem, ...]:
    items = json.loads(path.read_text(encoding="utf-8"))
    return tuple(NewsItem.model_validate(item) for item in items)


def load_news() -> tuple[NewsItem, ...]:
    return _news(get_settings().seed_dir / "news.json")


def _company_applications(session: Session, user: User) -> list[Application]:
    query = select(Application).where(Application.company_id == user.company_id)
    return list(session.scalars(query))


def _profile(user: User, applications: list[Application]) -> FeedProfile:
    """Профиль для новостей: ОКВЭД и сегмент компании, продукты и статусы её заявок."""
    company = user.company
    assert company is not None  # ClientUser гарантирует компанию
    active = [a for a in applications if a.status != ApplicationStatus.CANCELLED]
    return FeedProfile(
        okved_main=company.okved_main,
        segment=CompanySegment(company.segment),
        products={a.product.code: a.product.name for a in active if a.product is not None},
        statuses=frozenset(ApplicationStatus(a.status) for a in active),
    )


def _event_items(session: Session, applications: list[Application]) -> list[FeedItem]:
    numbers = {a.id: a.number for a in applications}
    if not numbers:
        return []
    query = (
        select(FeedEventRow)
        .where(FeedEventRow.application_id.in_(numbers))
        .order_by(FeedEventRow.created_at.desc())
    )
    return [
        FeedItem(
            id=row.id,
            kind=FeedItemKind.EVENT,
            title=row.title,
            body=row.body,
            created_at=row.created_at,
            read=row.read_at is not None,
            application_id=row.application_id,
            application_number=numbers[row.application_id],
            status=row.status,
            reasons=[],
            score=None,
        )
        for row in session.scalars(query)
    ]


def _news_items(profile: FeedProfile, now: datetime, limit: int) -> list[FeedItem]:
    return [
        FeedItem(
            id=ranked.news.id,
            kind=FeedItemKind.NEWS,
            title=ranked.news.title,
            body=ranked.news.body,
            created_at=ranked.news.published_at,
            read=True,  # контракт: отметка прочтения только у событий
            application_id=None,
            application_number=None,
            status=None,
            reasons=ranked.reasons,
            score=ranked.score,
        )
        for ranked in rank_news(load_news(), profile, now, limit)
    ]


def feed(
    session: Session,
    user: User,
    kind: FeedItemKind | None,
    news_limit: int,
    now: datetime | None = None,
) -> FeedResponse:
    applications = _company_applications(session, user)
    items: list[FeedItem] = []
    if kind in (None, FeedItemKind.EVENT):
        items += _event_items(session, applications)
    if kind in (None, FeedItemKind.NEWS):
        profile = _profile(user, applications)
        items += _news_items(profile, now or datetime.now(UTC), news_limit)
    return FeedResponse(
        items=items,
        ranking=FeedRanking(method=FeedRankingMethod.RULES, model_version=MODEL_VERSION),
    )


def mark_read(session: Session, user: User, event_id: UUID) -> None:
    """Повторная отметка ничего не меняет; чужое или несуществующее событие — 404."""
    row = session.get(FeedEventRow, event_id)
    application = session.get(Application, row.application_id) if row else None
    if row is None or application is None or application.company_id != user.company_id:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Событие не найдено")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        session.commit()

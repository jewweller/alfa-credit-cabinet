"""Персональная лента клиента: события по заявкам и новости по профилю (план, раздел 11).

События пишет `services.status.notify` при каждой смене статуса. Новости — `seed/news.json`,
вес и причины показа считает `domain.feed_ranking` (та же формула, что в моках фронта).

Порядок новостей может менять модель ML-команды (`ml.rank_feed`, docs/ml-ranking.md): только
при ML_RANKING_ENABLED=true, с таймаутом ML_TIMEOUT_SEC. Модель получает уже отфильтрованные
правилами новости и только переставляет их. Исключение, таймаут, ответ не по схеме или не те
кандидаты — порядок по правилам и предупреждение в лог; клиент разницы не заметит.

Временные решения backend (L1–L3, docs/analyst-questions.md, раздел 8) — аналитиком не
подтверждены:
  * события видны всем пользователям компании заявки — как в моках (один пользователь на
    компанию, план, раздел 2);
  * новости читаются из `seed/news.json` при первом запросе, отдельной таблицы нет;
  * выручка в профиле для модели — из последнего ответа ФНС по заявкам компании; заявок
    нет — пустая.
"""

import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.config import get_settings
from app.db.models import Application, EnrichmentResult, FeedEventRow, User
from app.domain.feed_ranking import MODEL_VERSION, FeedProfile, RankedNews, rank_news
from app.domain.state_machine import ApplicationStatus
from app.schemas.common import ErrorCode
from app.schemas.companies import CompanySegment
from app.schemas.feed import (
    FeedItem,
    FeedItemKind,
    FeedRanking,
    FeedRankingMethod,
    FeedReasonCode,
    FeedResponse,
    NewsItem,
)
from app.schemas.ml import (
    FeedRankCandidate,
    FeedRankRequest,
    FeedRankResponse,
    RankerApplication,
    RankerProfile,
    is_permutation,
)

log = logging.getLogger(__name__)

# Модель вызывается в отдельном потоке, чтобы ответ ленты не ждал её дольше таймаута.
_ml_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ml-rank")


@lru_cache
def _news(path: Path) -> tuple[NewsItem, ...]:
    items = json.loads(path.read_text(encoding="utf-8"))
    return tuple(NewsItem.model_validate(item) for item in items)


def load_news() -> tuple[NewsItem, ...]:
    return _news(get_settings().seed_dir / "news.json")


def _company_applications(session: Session, user: User) -> list[Application]:
    query = select(Application).where(Application.company_id == user.company_id)
    return list(session.scalars(query))


def _active(applications: list[Application]) -> list[Application]:
    return [a for a in applications if a.status != ApplicationStatus.CANCELLED]


def _profile(user: User, applications: list[Application]) -> FeedProfile:
    """Профиль для новостей: ОКВЭД и сегмент компании, продукты и статусы её заявок."""
    company = user.company
    assert company is not None  # ClientUser гарантирует компанию
    active = _active(applications)
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


# ── Ранжирование моделью ML ───────────────────────────────────────────────────


def _ranker() -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Функция модели. Пакет `ml` лежит рядом с `app` в образе API (docker-compose)."""
    from ml import rank_feed

    return rank_feed


def _revenue(session: Session, applications: list[Application]) -> dict[str, int]:
    if not applications:
        return {}
    query = (
        select(EnrichmentResult)
        .where(
            EnrichmentResult.application_id.in_([a.id for a in applications]),
            EnrichmentResult.source == "fns_tb",
            EnrichmentResult.status == "ok",
        )
        .order_by(EnrichmentResult.fetched_at.desc())
        .limit(1)
    )
    row = session.scalar(query)
    revenue = (row.response or {}).get("revenue", {}) if row else {}
    return {str(year): int(value) for year, value in revenue.items()}


def _ranker_profile(session: Session, user: User, applications: list[Application]) -> RankerProfile:
    """Профиль без ИНН, названия и данных БКИ (docs/ml-ranking.md, «Данные»)."""
    company = user.company
    assert company is not None
    return RankerProfile(
        kind=company.kind,
        okved_main=company.okved_main,
        region=company.region,
        segment=company.segment,
        registered_at=company.registered_at,
        revenue=_revenue(session, applications),
        applications=[
            RankerApplication(
                status=a.status,
                product_code=a.product.code if a.product else None,
                purpose=a.purpose,
            )
            for a in _active(applications)
        ],
    )


def _matched(ranked: RankedNews) -> list[FeedReasonCode]:
    return [reason.code for reason in ranked.reasons]


def _rank_with_ml(
    request: FeedRankRequest, candidates: list[RankedNews]
) -> tuple[list[RankedNews], str] | None:
    """Порядок модели или None — тогда остаётся порядок по правилам."""
    settings = get_settings()
    try:
        payload = request.model_dump(mode="json")
        raw = _ml_pool.submit(_ranker(), payload).result(timeout=settings.ml_timeout_sec)
        response = FeedRankResponse.model_validate(raw)
    except FutureTimeout:
        log.warning(
            "ML-ранжирование ленты: таймаут %s с, порядок по правилам", settings.ml_timeout_sec
        )
        return None
    except (ImportError, ValidationError) as error:
        log.warning("ML-ранжирование ленты: %s, порядок по правилам", error)
        return None
    except Exception:  # noqa: BLE001 — любой сбой модели не должен ломать ленту
        log.warning("ML-ранжирование ленты: сбой модели, порядок по правилам", exc_info=True)
        return None

    by_id = {c.news.id: c for c in candidates}
    if not is_permutation([item.id for item in response.ranking], by_id):
        log.warning("ML-ранжирование ленты: в ответе не те кандидаты, порядок по правилам")
        return None
    ranked = [
        RankedNews(
            news=by_id[item.id].news,
            score=item.score,
            # Свои причины модели — если есть; иначе остаются причины по правилам.
            reasons=item.reasons or by_id[item.id].reasons,
        )
        for item in response.ranking
    ]
    return ranked, response.model_version


def _ranked_news(
    session: Session,
    user: User,
    applications: list[Application],
    now: datetime,
    limit: int,
) -> tuple[list[RankedNews], FeedRanking]:
    rules = FeedRanking(method=FeedRankingMethod.RULES, model_version=MODEL_VERSION)
    profile = _profile(user, applications)
    if not get_settings().ml_ranking_enabled:
        return rank_news(load_news(), profile, now, limit), rules

    # Модели — все прошедшие фильтры новости в порядке правил; она только переставляет.
    candidates = rank_news(load_news(), profile, now, limit=len(load_news()))
    if not candidates:
        return [], rules
    request = FeedRankRequest(
        now=now,
        profile=_ranker_profile(session, user, applications),
        candidates=[
            FeedRankCandidate(**c.news.model_dump(), rule_score=c.score, matched=_matched(c))
            for c in candidates
        ],
    )
    result = _rank_with_ml(request, candidates)
    if result is None:
        return candidates[:limit], rules
    ranked, version = result
    return ranked[:limit], FeedRanking(method=FeedRankingMethod.ML, model_version=version)


def _news_items(ranked: list[RankedNews]) -> list[FeedItem]:
    return [
        FeedItem(
            id=r.news.id,
            kind=FeedItemKind.NEWS,
            title=r.news.title,
            body=r.news.body,
            created_at=r.news.published_at,
            read=True,  # контракт: отметка прочтения только у событий
            application_id=None,
            application_number=None,
            status=None,
            reasons=r.reasons,
            score=r.score,
        )
        for r in ranked
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
    ranking = FeedRanking(method=FeedRankingMethod.RULES, model_version=MODEL_VERSION)
    if kind in (None, FeedItemKind.EVENT):
        items += _event_items(session, applications)
    if kind in (None, FeedItemKind.NEWS):
        ranked, ranking = _ranked_news(
            session, user, applications, now or datetime.now(UTC), news_limit
        )
        items += _news_items(ranked)
    return FeedResponse(items=items, ranking=ranking)


def mark_read(session: Session, user: User, event_id: UUID) -> None:
    """Повторная отметка ничего не меняет; чужое или несуществующее событие — 404."""
    row = session.get(FeedEventRow, event_id)
    application = session.get(Application, row.application_id) if row else None
    if row is None or application is None or application.company_id != user.company_id:
        raise ApiError(404, ErrorCode.NOT_FOUND, "Событие не найдено")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        session.commit()

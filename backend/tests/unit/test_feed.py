import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.domain.feed_ranking import (
    OKVED_NAMES,
    WEIGHTS,
    FeedProfile,
    freshness,
    okved_group,
    rank_news,
)
from app.domain.state_machine import ApplicationStatus as S
from app.schemas.companies import CompanySegment
from app.schemas.feed import FeedReasonCode, NewsItem
from app.schemas.ml import (
    FeedRankRequest,
    FeedRankResponse,
    ProductRankItem,
    ProductRankRequest,
    ProductRankResponse,
    is_permutation,
)

SEED = get_settings().seed_dir
ML_EXAMPLES = Path(__file__).resolve().parents[3] / "docs" / "ml"
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)

NEWS = [NewsItem.model_validate(item) for item in json.loads((SEED / "news.json").read_text())]
COMPANIES = json.loads((SEED / "companies.json").read_text())
PRODUCTS = {p["code"]: p["name"] for p in json.loads((SEED / "products.json").read_text())}


def _profile(inn: str, *apps: tuple[str, S]) -> FeedProfile:
    company = next(c for c in COMPANIES if c["inn"] == inn)
    return FeedProfile(
        okved_main=company["okved_main"],
        segment=CompanySegment(company["segment"]),
        products={code: PRODUCTS[code] for code, _ in apps},
        statuses=frozenset(status for _, status in apps),
    )


def _titles(profile: FeedProfile) -> list[str]:
    return [r.news.title for r in rank_news(NEWS, profile, NOW)]


BAKERY = "7701000019"
KOVALEV = "500100001072"


def test_news_seed_is_consistent() -> None:
    assert 25 <= len(NEWS) <= 30
    assert len({n.id for n in NEWS}) == len(NEWS)
    for news in NEWS:
        assert set(news.tags.product) <= PRODUCTS.keys(), news.title
        assert all(len(g) == 2 and g.isdigit() for g in news.tags.okved), news.title
        assert S.CANCELLED not in news.tags.status, news.title


def test_every_demo_company_has_okved_name_and_some_news() -> None:
    for company in COMPANIES:
        assert company["okved_main"] in OKVED_NAMES
        assert len(_titles(_profile(company["inn"]))) >= 2, company["name"]


def test_feed_differs_between_bakery_and_kovalev() -> None:
    # План, демо: «лента у Пекарни и Ковалёва разная» — при одинаковом продукте и статусе.
    bakery = _titles(_profile(BAKERY, ("EXPRESS_WC", S.DRAFT)))
    kovalev = _titles(_profile(KOVALEV, ("EXPRESS_WC", S.DRAFT)))
    assert bakery[:3] != kovalev[:3]
    assert "Мука и сахар: чего ждать пекарням осенью" in bakery
    assert "Мука и сахар: чего ждать пекарням осенью" not in kovalev


def test_feed_changes_with_status() -> None:
    approved = _titles(_profile(BAKERY, ("EXPRESS_WC", S.APPROVED)))
    issued = _titles(_profile(BAKERY, ("EXPRESS_WC", S.ISSUED)))
    assert "Что проверить перед подписанием договора" in approved
    assert "Что проверить перед подписанием договора" not in issued
    assert "Деньги выданы: как не пропустить первый платёж" in issued


def test_okved_and_status_tags_filter_and_every_item_has_reason() -> None:
    profile = _profile(BAKERY, ("EXPRESS_WC", S.APPROVED))
    for ranked in rank_news(NEWS, profile, NOW, limit=100):
        tags = ranked.news.tags
        assert not tags.okved or okved_group(profile.okved_main) in tags.okved
        assert not tags.status or set(tags.status) & profile.statuses
        assert ranked.reasons
        weights = [WEIGHTS.get(r.code, 0) for r in ranked.reasons]
        assert weights == sorted(weights, reverse=True)


def test_untagged_news_is_general_and_tagged_without_match_is_hidden() -> None:
    reasons = {
        r.news.title: [x.code for x in r.reasons]
        for r in rank_news(NEWS, _profile(BAKERY), NOW, limit=100)
    }
    assert reasons["Налоговый календарь на ноябрь"] == [FeedReasonCode.GENERAL]
    assert "Нет кредитной истории: с чего начать" not in reasons  # только для micro


def test_top_item_reason_matches_plan_example() -> None:
    top = rank_news(NEWS, _profile(BAKERY), NOW)[0]
    assert top.reasons[0].text == "Ваш ОКВЭД 10.71 — производство хлеба и мучных изделий"


def test_freshness() -> None:
    assert freshness(NOW, NOW) == 1
    assert freshness(NOW + timedelta(days=1), NOW) == 1
    assert freshness(NOW - timedelta(days=15), NOW) == pytest.approx(0.5)
    assert freshness(NOW - timedelta(days=40), NOW) == 0


@pytest.mark.parametrize(
    ("request_model", "response_model", "name", "id_field"),
    [
        (FeedRankRequest, FeedRankResponse, "feed-rank", "id"),
        (ProductRankRequest, ProductRankResponse, "product-rank", "product_id"),
    ],
)
def test_ml_examples_match_schemas(request_model, response_model, name, id_field) -> None:
    request = request_model.model_validate_json((ML_EXAMPLES / f"{name}.request.json").read_text())
    response = response_model.model_validate_json(
        (ML_EXAMPLES / f"{name}.response.json").read_text()
    )
    candidate_ids = [c.id if id_field == "id" else c.product.id for c in request.candidates]
    assert is_permutation([getattr(item, id_field) for item in response.ranking], candidate_ids)


def test_is_permutation_rejects_missing_and_extra() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    assert is_permutation([b, a], [a, b])
    assert not is_permutation([a], [a, b])
    assert not is_permutation([a, b, c], [a, b])
    assert not is_permutation([a, c], [a, b])


def test_ml_response_validation() -> None:
    same = uuid4()
    with pytest.raises(ValidationError, match="повторяются"):
        FeedRankResponse.model_validate(
            {"model_version": "x", "ranking": [{"id": same, "score": 1}, {"id": same, "score": 0}]}
        )
    with pytest.raises(ValidationError):
        ProductRankItem.model_validate({"product_id": same, "score": 1.5})
    with pytest.raises(ValidationError):
        ProductRankItem.model_validate({"product_id": same, "score": 0.5, "reasons": ["я" * 121]})


def test_frontend_mock_news_match_seed() -> None:
    # Docker собирает фронт только из frontend/, поэтому моки держат копию новостей.
    mock = Path(__file__).resolve().parents[3] / "frontend" / "src" / "mocks" / "news.json"
    assert json.loads(mock.read_text()) == json.loads((SEED / "news.json").read_text()), (
        "frontend/src/mocks/news.json расходится с seed/news.json — скопируйте заново"
    )

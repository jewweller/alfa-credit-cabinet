"""Лента: события при смене статуса, новости по профилю, фильтры, отметка прочтения, доступ."""

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import auth_headers
from demo_flows import BAKERY, KOVALEV, MELNIKOVA, MIRAGE, create_draft, submit_demo
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import User
from app.domain.feed_ranking import MODEL_VERSION, rank_news
from app.services import feed as feed_service

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[3]


def _feed(client: TestClient, headers: dict, **params) -> dict:  # noqa: ANN003
    response = client.get("/api/v1/feed", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _events(client: TestClient, headers: dict) -> list[dict]:
    return _feed(client, headers, kind="event")["items"]


def _read(client: TestClient, event_id: str, headers: dict):  # noqa: ANN202
    return client.post(f"/api/v1/feed/events/{event_id}/read", headers=headers)


# ── События ─────────────────────────────────────────────────────────────────


def test_submit_creates_events_newest_first(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)
    n = app["number"]

    events = _events(client, headers)

    # ENRICHMENT и SCORING — промежуточные шаги, событий у них нет (как в моках).
    assert [(e["status"], e["title"]) for e in events] == [
        ("APPROVED", f"Заявка №{n} одобрена"),
        ("SUBMITTED", f"Заявка №{n} отправлена"),
    ]
    first = events[0]
    assert first["body"] == "Посмотрите предложение и график платежей."
    assert first["kind"] == "event" and first["read"] is False
    assert (first["application_id"], first["application_number"]) == (app["id"], n)
    assert (first["reasons"], first["score"]) == ([], None)


def test_whole_client_path_leaves_trail_of_events(client: TestClient) -> None:
    app, headers = submit_demo(client, *BAKERY)
    offer = app["active_offer"]["id"]
    client.post(f"/api/v1/applications/{app['id']}/offers/{offer}/accept", headers=headers)
    code = client.post(f"/api/v1/applications/{app['id']}/signing/code", headers=headers).json()
    client.post(
        f"/api/v1/applications/{app['id']}/signing/confirm",
        json={"code": code["code"]},
        headers=headers,
    )

    statuses = [e["status"] for e in _events(client, headers)]

    # SIGNED события не даёт: за ним сразу идёт выдача.
    assert statuses == ["ISSUED", "SIGNING", "APPROVED", "SUBMITTED"]


def test_cancel_and_underwriter_decision_create_events(client: TestClient) -> None:
    draft, headers = create_draft(client, *BAKERY)
    client.post(f"/api/v1/applications/{draft['id']}/cancel", headers=headers)
    mirage, mirage_headers = submit_demo(client, *MIRAGE)
    client.post(
        f"/api/v1/bank/applications/{mirage['id']}/decision",
        json={"outcome": "rejected", "reason_code": "low_score"},
        headers=auth_headers(client, "underwriter@demo.local"),
    )

    assert [e["status"] for e in _events(client, headers)] == ["CANCELLED"]
    assert [e["status"] for e in _events(client, mirage_headers)] == [
        "REJECTED",
        "MANUAL_REVIEW",
        "SUBMITTED",
    ]


def test_client_sees_only_own_events(client: TestClient) -> None:
    submit_demo(client, *BAKERY)
    _, kovalev = submit_demo(client, *KOVALEV)

    events = _events(client, kovalev)

    assert [e["status"] for e in events] == ["COUNTER_OFFER", "SUBMITTED"]


# ── Новости ─────────────────────────────────────────────────────────────────


def test_news_follow_rules_ranking_with_reasons(client: TestClient) -> None:
    headers = auth_headers(client, "bakery@demo.local")

    body = _feed(client, headers, kind="news")

    assert body["ranking"] == {"method": "rules", "model_version": MODEL_VERSION}
    news = body["items"]
    assert 0 < len(news) <= 10
    assert all(item["kind"] == "news" and item["read"] is True for item in news)
    assert all(item["reasons"] for item in news)
    scores = [item["score"] for item in news]
    assert scores == sorted(scores, reverse=True)
    assert news[0]["reasons"][0]["code"] == "okved"  # Пекарня: ОКВЭД 10.71


def test_news_match_domain_ranking_for_client_profile(engine: Engine) -> None:
    """Порядок и причины — ровно как у domain.feed_ranking (его же повторяют моки фронта)."""
    with Session(engine) as session:
        user = session.query(User).filter_by(email="bakery@demo.local").one()
        response = feed_service.feed(session, user, None, 10, now=NOW)
        profile = feed_service._profile(user, feed_service._company_applications(session, user))

    expected = rank_news(feed_service.load_news(), profile, NOW, 10)
    news = [i for i in response.items if i.kind == "news"]
    assert [(i.id, i.score, i.reasons) for i in news] == [
        (r.news.id, r.score, r.reasons) for r in expected
    ]


def test_news_change_with_application_status(client: TestClient) -> None:
    headers = auth_headers(client, "bakery@demo.local")
    before = {item["id"] for item in _feed(client, headers, kind="news", news_limit=30)["items"]}

    submit_demo(client, *BAKERY)
    after = _feed(client, headers, kind="news", news_limit=30)["items"]

    assert {item["id"] for item in after} != before
    assert any(r["code"] == "status" for item in after for r in item["reasons"])


def test_filters_and_news_limit(client: TestClient) -> None:
    _, headers = submit_demo(client, *BAKERY)

    everything = _feed(client, headers)["items"]
    limited = _feed(client, headers, kind="news", news_limit=3)["items"]

    kinds = [item["kind"] for item in everything]
    assert kinds == sorted(kinds)  # события сверху, новости ниже
    assert len(limited) == 3
    assert client.get("/api/v1/feed", params={"news_limit": 31}, headers=headers).status_code == 422


# ── Отметка прочтения ───────────────────────────────────────────────────────


def test_mark_read_is_idempotent(client: TestClient) -> None:
    _, headers = submit_demo(client, *BAKERY)
    event = _events(client, headers)[0]

    first = _read(client, event["id"], headers)
    again = _read(client, event["id"], headers)

    assert first.status_code == again.status_code == 204
    assert _events(client, headers)[0]["read"] is True
    assert _events(client, headers)[1]["read"] is False


def test_other_client_event_and_unknown_are_404(client: TestClient) -> None:
    _, headers = submit_demo(client, *BAKERY)
    event = _events(client, headers)[0]
    stranger = auth_headers(client, "kovalev@demo.local")

    assert _read(client, event["id"], stranger).status_code == 404
    assert _read(client, "00000000-0000-4000-8000-000000000000", headers).status_code == 404
    assert _events(client, headers)[0]["read"] is False


def test_feed_is_for_clients_only(client: TestClient) -> None:
    _, headers = submit_demo(client, *BAKERY)
    event = _events(client, headers)[0]
    underwriter = auth_headers(client, "underwriter@demo.local")

    assert client.get("/api/v1/feed", headers=underwriter).status_code == 403
    assert _read(client, event["id"], underwriter).status_code == 403
    assert client.get("/api/v1/feed").status_code == 401


# ── Ранжирование моделью ML ─────────────────────────────────────────────────


@pytest.fixture
def ml_enabled(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setattr(get_settings(), "ml_ranking_enabled", True)
    return monkeypatch


def _rules_order(client: TestClient, headers: dict) -> list[str]:
    return [i["id"] for i in _feed(client, headers, kind="news", news_limit=30)["items"]]


def test_ml_reorders_news_and_reports_method(client: TestClient, ml_enabled) -> None:  # noqa: ANN001
    _, headers = submit_demo(client, *BAKERY)
    seen: list[dict] = []

    def reverse(payload: dict) -> dict:
        seen.append(payload)
        candidates = payload["candidates"][::-1]
        # Код причины — из реальных совпадений новости: иначе бэкенд её не покажет.
        reason = [{"code": candidates[0]["matched"][0], "text": "Модель так решила"}]
        return {
            "model_version": "test-ranker-1",
            "ranking": [
                {
                    "id": c["id"],
                    "score": 1 - n / len(candidates),
                    "reasons": reason if n == 0 else [],
                }
                for n, c in enumerate(candidates)
            ],
        }

    ml_enabled.setattr(feed_service, "_ranker", lambda: reverse)
    body = _feed(client, headers, kind="news", news_limit=30)

    assert body["ranking"] == {"method": "ml", "model_version": "test-ranker-1"}
    candidates = [c["id"] for c in seen[0]["candidates"]]
    assert [i["id"] for i in body["items"]] == candidates[::-1]
    first_code = seen[0]["candidates"][-1]["matched"][0]
    assert body["items"][0]["reasons"] == [{"code": first_code, "text": "Модель так решила"}]
    assert body["items"][1]["reasons"]  # модель причин не дала — остались причины правил
    profile = seen[0]["profile"]
    # Только поля RankerProfile: без ИНН, названия компании и данных БКИ.
    assert set(profile) == {
        "kind",
        "okved_main",
        "region",
        "segment",
        "registered_at",
        "revenue",
        "applications",
    }
    assert set(profile["applications"][0]) == {"status", "product_code", "purpose"}
    assert profile["revenue"] == {"2024": 21428571, "2025": 24000000}  # из ответа ФНС
    assert profile["applications"][0]["status"] == "APPROVED"


@pytest.mark.parametrize(
    "broken",
    [
        lambda payload: (_ for _ in ()).throw(RuntimeError("модель упала")),
        lambda payload: {"model_version": "x", "ranking": []},  # не те кандидаты
        lambda payload: {
            "model_version": "x",
            "ranking": [{"id": c["id"], "score": 5} for c in payload["candidates"]],
        },  # score вне 0…1
    ],
)
def test_broken_model_falls_back_to_rules(client: TestClient, ml_enabled, broken) -> None:  # noqa: ANN001
    headers = auth_headers(client, "bakery@demo.local")
    ml_enabled.setattr(get_settings(), "ml_ranking_enabled", False)
    expected = _rules_order(client, headers)
    ml_enabled.setattr(get_settings(), "ml_ranking_enabled", True)
    ml_enabled.setattr(feed_service, "_ranker", lambda: broken)

    body = _feed(client, headers, kind="news", news_limit=30)

    assert body["ranking"]["method"] == "rules"
    assert [i["id"] for i in body["items"]] == expected


def test_slow_model_falls_back_to_rules(client: TestClient, ml_enabled) -> None:  # noqa: ANN001
    headers = auth_headers(client, "bakery@demo.local")
    ml_enabled.setattr(get_settings(), "ml_timeout_sec", 0.05)

    def slow(payload: dict) -> dict:
        time.sleep(0.5)
        return {}

    ml_enabled.setattr(feed_service, "_ranker", lambda: slow)

    assert _feed(client, headers, kind="news")["ranking"]["method"] == "rules"


def test_real_model_ranks_feed(client: TestClient, ml_enabled) -> None:  # noqa: ANN001
    """Настоящая модель из ml/: логистическая регрессия переставляет те же новости и даёт
    свои причины, которые проходят проверку бэкенда."""
    ml_enabled.syspath_prepend(str(REPO_ROOT))
    _, headers = submit_demo(client, *MELNIKOVA)  # INFO_REQUESTED: есть подсказки к шагу
    ml_enabled.setattr(get_settings(), "ml_ranking_enabled", False)
    rules = _feed(client, headers, kind="news", news_limit=30)["items"]
    ml_enabled.setattr(get_settings(), "ml_ranking_enabled", True)

    body = _feed(client, headers, kind="news", news_limit=30)

    assert body["ranking"] == {"method": "ml", "model_version": "feed-logreg-1.0.0"}
    items = body["items"]
    assert sorted(i["id"] for i in items) == sorted(i["id"] for i in rules)
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True) and all(0 < s < 1 for s in scores)
    rule_codes = {i["id"]: {r["code"] for r in i["reasons"]} for i in rules}
    for item in items:
        assert 1 <= len(item["reasons"]) <= 2
        assert {r["code"] for r in item["reasons"]} <= rule_codes[item["id"]]
    assert any(
        r["text"] == "Подсказка к текущему этапу вашей заявки" for i in items for r in i["reasons"]
    )


def test_broken_model_file_falls_back_to_rules(  # noqa: ANN001
    client: TestClient, ml_enabled, tmp_path: Path
) -> None:
    ml_enabled.syspath_prepend(str(REPO_ROOT))
    from ml.synth import ranking

    bad = tmp_path / "model.json"
    bad.write_text("{}")
    ml_enabled.setattr(ranking, "MODEL_PATH", bad)
    ranking._model.cache_clear()
    try:
        body = _feed(client, auth_headers(client, "bakery@demo.local"), kind="news")
    finally:
        ranking._model.cache_clear()

    assert body["ranking"] == {"method": "rules", "model_version": MODEL_VERSION}
    assert body["items"]


def _same_order(payload: dict, **item) -> dict:  # noqa: ANN003
    """Ответ модели в порядке бэкенда; `item` дописывается в каждый элемент."""
    return {
        "model_version": "test-ranker-1",
        "ranking": [{"id": c["id"], "score": 0.5, **item} for c in payload["candidates"]],
    }


def _bad_ids(payload: dict, ids: list[str]) -> dict:
    return {"model_version": "x", "ranking": [{"id": i, "score": 0.5} for i in ids]}


@pytest.mark.parametrize(
    "broken",
    [
        # повтор кандидата
        lambda p: _bad_ids(p, [p["candidates"][0]["id"]] * len(p["candidates"])),
        # чужая новость вместо одной из своих
        lambda p: _bad_ids(
            p, [c["id"] for c in p["candidates"][1:]] + ["00000000-0000-4000-8000-000000000000"]
        ),
        # пустая версия модели
        lambda p: {**_same_order(p), "model_version": "  "},
        # причина длиннее 120 символов
        lambda p: _same_order(p, reasons=[{"code": "general", "text": "х" * 121}]),
        # больше двух причин
        lambda p: _same_order(p, reasons=[{"code": "general", "text": "да"}] * 3),
        # неизвестный код причины
        lambda p: _same_order(p, reasons=[{"code": "salary", "text": "да"}]),
    ],
    ids=["duplicate", "foreign", "no-version", "long-reason", "three-reasons", "unknown-code"],
)
def test_invalid_model_answer_falls_back_to_rules(  # noqa: ANN001
    client: TestClient, ml_enabled, broken
) -> None:
    _, headers = submit_demo(client, *BAKERY)
    ml_enabled.setattr(get_settings(), "ml_ranking_enabled", False)
    expected = _feed(client, headers, kind="news", news_limit=30)["items"]
    ml_enabled.setattr(get_settings(), "ml_ranking_enabled", True)
    ml_enabled.setattr(feed_service, "_ranker", lambda: broken)

    body = _feed(client, headers, kind="news", news_limit=30)

    assert body["ranking"] == {"method": "rules", "model_version": MODEL_VERSION}
    assert body["items"] == expected


def test_model_reasons_are_checked_per_news(client: TestClient, ml_enabled) -> None:  # noqa: ANN001
    """Пустая причина и причина с несовпавшим кодом заменяются причинами правил;
    причина ровно 120 символов принимается. Порядок модели при этом сохраняется."""
    _, headers = submit_demo(client, *BAKERY)
    ml_enabled.setattr(get_settings(), "ml_ranking_enabled", False)
    rules = {
        i["id"]: i["reasons"] for i in _feed(client, headers, kind="news", news_limit=30)["items"]
    }
    ml_enabled.setattr(get_settings(), "ml_ranking_enabled", True)
    long_text = "а" * 120

    def answer(payload: dict) -> dict:
        first, second, third = payload["candidates"][:3]
        foreign = next(
            code
            for code in ("okved", "status", "product", "segment", "general")
            if code not in second["matched"]
        )
        reasons = {
            first["id"]: [{"code": first["matched"][0], "text": long_text}],
            second["id"]: [{"code": foreign, "text": "Модель придумала совпадение"}],
            third["id"]: [{"code": third["matched"][0], "text": "   "}],
        }
        return {
            "model_version": "test-ranker-1",
            "ranking": [
                {"id": c["id"], "score": 0.5, "reasons": reasons.get(c["id"], [])}
                for c in payload["candidates"]
            ],
        }

    ml_enabled.setattr(feed_service, "_ranker", lambda: answer)
    items = _feed(client, headers, kind="news", news_limit=30)["items"]

    assert items[0]["reasons"] == [{"code": items[0]["reasons"][0]["code"], "text": long_text}]
    assert items[1]["reasons"] == rules[items[1]["id"]]  # несовпавший код — причины правил
    assert items[2]["reasons"] == rules[items[2]["id"]]  # пустой текст — причины правил


def test_empty_feed_does_not_call_model(client: TestClient, ml_enabled) -> None:  # noqa: ANN001
    headers = auth_headers(client, "bakery@demo.local")
    calls: list[dict] = []
    ml_enabled.setattr(feed_service, "load_news", lambda: ())
    ml_enabled.setattr(feed_service, "_ranker", lambda: calls.append)

    body = _feed(client, headers, kind="news")

    assert body == {"items": [], "ranking": {"method": "rules", "model_version": MODEL_VERSION}}
    assert calls == []


def test_ml_does_not_touch_credit_decision(client: TestClient, ml_enabled) -> None:  # noqa: ANN001
    """Модель ленты не участвует в скоринге и решении: исход и оффер Пекарни те же."""
    ml_enabled.setattr(feed_service, "_ranker", lambda: lambda p: 1 / 0)

    app, headers = submit_demo(client, *BAKERY)
    _feed(client, headers)

    assert app["status"] == "APPROVED"
    offer = app["active_offer"]
    assert (offer["amount"], offer["term_months"], offer["rate"], offer["monthly_payment"]) == (
        "3000000.00",
        12,
        "18.00",
        "275039.98",
    )

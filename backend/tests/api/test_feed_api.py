"""Лента: события при смене статуса, новости по профилю, фильтры, отметка прочтения, доступ."""

from datetime import UTC, datetime

from conftest import auth_headers
from demo_flows import BAKERY, KOVALEV, MIRAGE, create_draft, submit_demo
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.models import User
from app.domain.feed_ranking import MODEL_VERSION, rank_news
from app.services import feed as feed_service

NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


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

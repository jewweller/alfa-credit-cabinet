"""Остальные тестовые ИНН из docs/plan.md, раздел 8, через настоящий submit."""

from conftest import auth_headers
from demo_flows import MELNIKOVA, MIRAGE, SBOY, VEKTOR, rows, submit_demo
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.db.models import DecisionRow, EnrichmentResult, ScoringResultRow


def test_vektor_current_overdue_is_rejected_by_r2(client: TestClient, engine: Engine) -> None:
    app, _ = submit_demo(client, *VEKTOR)

    assert app["status"] == "REJECTED"
    assert app["decision"]["reason_code"] == "bankruptcy_or_overdue"
    [decision] = rows(engine, DecisionRow, app["id"])
    assert decision.reason_code == "R2_OVERDUE"


def test_mirage_grade_d_goes_to_manual_review(client: TestClient, engine: Engine) -> None:
    app, _ = submit_demo(client, *MIRAGE)

    assert app["status"] == "MANUAL_REVIEW"
    [scoring] = rows(engine, ScoringResultRow, app["id"])
    # План, раздел 8: «→ 40 баллов, грейд D».
    assert (scoring.total_score, scoring.grade) == (40, "D")
    points = {f["id"]: f["points"] for f in scoring.factors["factors"]}
    assert points == {"F1": 15, "F2": 5, "F3": 20, "F4": 0, "F5": 0, "F6": 0}
    [decision] = rows(engine, DecisionRow, app["id"])
    assert decision.reason_code == "R7_GRADE_D"


def test_sboy_bki_503_goes_to_manual_review_by_r3(client: TestClient, engine: Engine) -> None:
    app, _ = submit_demo(client, *SBOY)

    assert app["status"] == "MANUAL_REVIEW"
    assert app["decision"]["outcome"] == "manual_review"
    [decision] = rows(engine, DecisionRow, app["id"])
    assert decision.reason_code == "R3_SOURCE_UNAVAILABLE"
    [bki] = [r for r in rows(engine, EnrichmentResult, app["id"]) if r.source == "bki"]
    assert (bki.status, bki.attempts, bki.error) == ("unavailable", 3, "HTTP 503")


def test_melnikova_score_matches_plan(client: TestClient, engine: Engine) -> None:
    app, _ = submit_demo(client, *MELNIKOVA)

    [scoring] = rows(engine, ScoringResultRow, app["id"])
    assert (scoring.total_score, scoring.grade) == (66, "B")  # план, раздел 7


def test_new_demo_accounts_log_in_with_their_company(client: TestClient) -> None:
    for email, inn in [
        ("vektor@demo.local", "7701000033"),
        ("mirage@demo.local", "7701000058"),
        ("sboy@demo.local", "7701000065"),
    ]:
        me = client.get("/api/v1/auth/me", headers=auth_headers(client, email)).json()
        assert me["company"]["inn"] == inn

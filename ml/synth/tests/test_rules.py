import pytest
from ml.synth.money import maximum_amount, monthly_payment
from ml.synth.rules import Decision, Score, age_years


def test_bakery(demo):
    company, request, candidate, fns, bki, engine = demo
    score = engine.score(company, request, candidate, fns, bki)
    assert score.total == 100 and score.grade == "A"
    decision = engine.decide(company, request, candidate, fns, bki)
    assert decision.outcome == "approved" and decision.rule == "R9"
    assert decision.offer["monthly_payment"] == "275039.98"


def test_kovalev(demo):
    company, request, candidate, fns, bki, engine = demo
    company["registered_at"] = "2023-10-22"
    request.update(
        amount_requested="2000000.00",
        revenue_12m="6000000.00",
        existing_payments_monthly="60000.00",
    )
    candidate["amount"] = "2000000.00"
    fns["revenue"] = {"2024": "5714285.71", "2025": "6000000.00"}
    bki.update(max_overdue_days_24m=20, loans=[{"monthly_payment": "60000.00"}])
    assert engine.score(company, request, candidate, fns, bki).total == 69
    decision = engine.decide(company, request, candidate, fns, bki)
    assert (decision.outcome, decision.rule) == ("counter_offer", "R10")
    assert (decision.offer["amount"], decision.offer["term_months"], decision.offer["rate"]) == (
        "2000000.00",
        24,
        "20.00",
    )


def test_melnikova_and_documents(demo):
    company, request, candidate, fns, bki, engine = demo
    company["registered_at"] = "2025-04-22"
    request.update(revenue_12m="12000000.00", existing_payments_monthly="0.00")
    candidate["amount"] = "1500000.00"
    fns["revenue"] = {"2025": "7000000.00"}
    bki.update(has_history=False, loans=[])
    assert engine.score(company, request, candidate, fns, bki).total == 66
    assert engine.decide(company, request, candidate, fns, bki) == Decision("info_requested", "R4")
    request["documents_provided"] = True
    assert engine.decide(company, request, candidate, fns, bki) == Decision("manual_review", "R4")


@pytest.mark.parametrize("status", ["LIQUIDATING", "LIQUIDATED"])
def test_stroy_and_rule_precedence(demo, status):
    company, request, candidate, fns, bki, engine = demo
    company["status"] = status
    bki["bankruptcy"] = True
    fns["available"] = False
    assert engine.score(company, request, candidate, fns, bki).total >= 0
    assert engine.decide(company, request, candidate, fns, bki) == Decision(
        "rejected", "R1", "company_inactive"
    )


def test_r2_r3_r5_in_order(demo):
    company, request, candidate, fns, bki, engine = demo
    bki["current_overdue_days"] = 91
    assert engine.decide(company, request, candidate, fns, bki).rule == "R2"
    bki["available"] = False
    assert engine.decide(company, request, candidate, fns, bki).rule == "R3"
    bki.update(available=True, current_overdue_days=90)
    candidate.update(product_code="EQUIPMENT", amount="10000000.01")
    assert engine.decide(company, request, candidate, fns, bki).rule == "R5"


@pytest.mark.parametrize(
    ("grade", "rule", "outcome"),
    [("E", "R6", "rejected"), ("D", "R7", "manual_review"), ("C", "R8", "counter_offer")],
)
def test_grade_decisions(demo, monkeypatch, grade, rule, outcome):
    company, request, candidate, fns, bki, engine = demo
    monkeypatch.setattr(engine, "score", lambda *args: Score(0, grade, 0.2, ()))
    result = engine.decide(company, request, candidate, fns, bki)
    assert (result.rule, result.outcome) == (rule, outcome)
    if grade == "C":
        assert float(result.offer["amount"]) <= 1500000
        assert result.offer["rate"] == "22.00"


def test_r10_rejects_when_no_product_is_affordable(demo, monkeypatch):
    company, request, candidate, fns, bki, engine = demo
    bki["loans"] = [{"monthly_payment": "2000000.00"}]
    monkeypatch.setattr(engine, "score", lambda *args: Score(80, "A", 1.2, ()))
    assert engine.decide(company, request, candidate, fns, bki) == Decision(
        "rejected", "R10", "no_suitable_terms"
    )


def test_r10_can_try_another_product(demo, monkeypatch):
    company, request, candidate, fns, bki, engine = demo
    request.update(purpose="cash_gap", revenue_12m="400000.00")
    candidate["amount"] = "300000.00"
    fns["revenue"] = {"2025": "400000.00"}
    bki["loans"] = []
    # Express minimum 300k does not fit at 24m, overdraft minimum 100k does at 12m.
    monkeypatch.setattr(engine, "score", lambda *args: Score(80, "A", 1.0, ()))
    decision = engine.decide(company, request, candidate, fns, bki)
    assert decision.outcome == "counter_offer"
    assert decision.offer["product_code"] == "OVERDRAFT"


@pytest.mark.parametrize(
    ("registered", "expected"),
    [("2025-10-22", 8), ("2024-10-22", 15), ("2021-10-22", 15), ("2021-10-21", 20)],
)
def test_calendar_age_boundaries(demo, registered, expected):
    company, request, candidate, fns, bki, engine = demo
    company["registered_at"] = registered
    assert engine.score(company, request, candidate, fns, bki).factors[0] == expected
    assert age_years(company, request) >= 1


@pytest.mark.parametrize("budget", [0, 0.01, 125000.12, 1000000])
def test_affordable_principal_respects_rounded_payment(budget):
    amount = maximum_amount(budget, 20, 24, 5000000)
    assert float(monthly_payment(amount, 20, 24)) <= budget
    if 0 < float(amount) < 5000000:
        assert float(monthly_payment(float(amount) + 0.01, 20, 24)) > budget

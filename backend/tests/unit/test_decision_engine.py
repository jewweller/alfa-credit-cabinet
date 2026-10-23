"""R1–R10: каждое правило, границы порогов и приоритет (срабатывает первое)."""

from dataclasses import replace
from decimal import Decimal as D

import pytest
from engine_data import (
    BAKERY,
    EQUIPMENT,
    KOVALEV,
    MELNIKOVA,
    PRODUCTS,
    REF,
    registered,
    request,
    sources,
)

from app.decision.engine import decide
from app.scoring.config import load_config, parse_config
from app.scoring.engine import score
from app.scoring.inputs import BkiLoan, BkiReport, FnsProfile, RegistryData, Source


def _decide(req, src, proof: bool = False, products=PRODUCTS, config=None):  # noqa: ANN001, ANN202
    scoring = score(req, src, config=config, reference_date=REF)
    return decide(req, src, scoring, products, proof, config=config)


def _fired_rules(decision) -> list[str]:  # noqa: ANN001
    return [c.rule for c in decision.checks]


# ── Примеры из плана (раздел 7) ──────────────────────────────────────────────


def test_bakery_is_approved_on_requested_terms() -> None:
    decision = _decide(*BAKERY)

    assert (decision.outcome, decision.reason_code) == ("APPROVED", "R9_APPROVED")
    offer = decision.offer
    assert (offer.amount, offer.term_months, offer.rate) == (D(3_000_000), 12, D(18))
    assert offer.monthly_payment == D("275040.00")
    assert _fired_rules(decision) == [f"R{n}" for n in range(1, 10)]
    assert decision.config_version == "1.0.0"


def test_kovalev_gets_longer_term_at_grade_b_rate() -> None:
    decision = _decide(*KOVALEV)

    assert (decision.outcome, decision.reason_code) == ("COUNTER_OFFER", "R10_COUNTER_OFFER")
    offer = decision.offer
    assert (offer.product.code, offer.amount, offer.term_months) == ("EXPRESS_WC", D(2_000_000), 24)
    assert offer.rate == D(20)
    assert offer.monthly_payment == D("101792.00")
    assert round(offer.debt_load_pct, 1) == D("32.4")


def test_melnikova_info_requested_then_manual_review_after_document() -> None:
    first = _decide(*MELNIKOVA)
    second = _decide(*MELNIKOVA, proof=True)

    assert (first.outcome, first.reason_code) == ("INFO_REQUESTED", "R4_REVENUE_PROOF_REQUIRED")
    assert [i.kind for i in first.info_request_items] == ["tax_return"]
    assert (second.outcome, second.reason_code) == ("MANUAL_REVIEW", "R4_REVENUE_MISMATCH_REVIEW")


def test_liquidated_company_is_rejected_but_scored() -> None:
    req, _ = BAKERY
    src = sources(status="LIQUIDATED")

    scoring = score(req, src, reference_date=REF)
    decision = decide(req, src, scoring, PRODUCTS)

    assert scoring.total == 100  # скоринг посчитан, хотя решение — отказ
    assert (decision.outcome, decision.reason_code) == ("REJECTED", "R1_LIQUIDATED")
    assert decision.client_reason == "company_inactive"
    assert "ЕГРЮЛ" in decision.client_message
    assert _fired_rules(decision) == ["R1"]


# ── R1–R3: стоп-факторы и источники ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("registry", "code"),
    [
        (Source.ok(RegistryData("LIQUIDATING", registered(7))), "R1_LIQUIDATING"),
        (Source.not_found(), "R1_NOT_FOUND"),
    ],
)
def test_r1_registry(registry: Source, code: str) -> None:
    req, src = KOVALEV

    decision = _decide(req, replace(src, registry=registry))

    assert (decision.outcome, decision.reason_code) == ("REJECTED", code)
    assert "ЕГРИП" in decision.client_message  # ИП — реестр ЕГРИП


@pytest.mark.parametrize(
    ("bki", "code"),
    [
        (BkiReport(True, True), "R2_BANKRUPTCY"),
        (BkiReport(True, False, (BkiLoan(D(0), 120, 91),)), "R2_OVERDUE"),
    ],
)
def test_r2_credit_stop_factors(bki: BkiReport, code: str) -> None:
    decision = _decide(request(), sources(bki=bki))

    assert (decision.outcome, decision.reason_code) == ("REJECTED", code)
    assert decision.client_reason == "bankruptcy_or_overdue"
    # Клиенту — без подробностей БКИ: ни дней, ни сумм.
    assert not any(ch.isdigit() for ch in decision.client_message + decision.client_next_step)


def test_r2_overdue_of_exactly_90_days_is_not_a_stop_factor() -> None:
    bki = BkiReport(True, False, (BkiLoan(D(0), 90, 90),))

    assert _decide(request(), sources(bki=bki)).reason_code != "R2_OVERDUE"


@pytest.mark.parametrize("source", ["registry", "fns", "bki"])
def test_r3_any_required_source_unavailable(source: str) -> None:
    req, src = BAKERY

    decision = _decide(req, replace(src, **{source: Source.unavailable()}))

    assert (decision.outcome, decision.reason_code) == ("MANUAL_REVIEW", "R3_SOURCE_UNAVAILABLE")


def test_r3_lists_every_unavailable_source() -> None:
    req, src = BAKERY

    decision = _decide(req, replace(src, fns=Source.unavailable(), bki=Source.unavailable()))

    assert "ФНС" in decision.staff_message and "БКИ" in decision.staff_message


def test_stop_factor_has_priority_over_unavailable_source() -> None:
    req, src = BAKERY

    decision = _decide(req, replace(sources(status="LIQUIDATED"), bki=Source.unavailable()))

    assert decision.reason_code == "R1_LIQUIDATED"
    assert src  # исходные данные не изменились


# ── R4–R7 ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("fns_revenue", "fired"),
    [(D(10_000_000), False), (D("9230769"), True)],  # 12 млн к 10 млн = 20 %, к 9,23 млн > 30 %
)
def test_r4_threshold(fns_revenue: D, fired: bool) -> None:
    req, src = MELNIKOVA
    src = replace(src, fns=Source.ok(FnsProfile({2025: fns_revenue}, D(0), {})))

    decision = _decide(req, src)

    assert (decision.reason_code == "R4_REVENUE_PROOF_REQUIRED") is fired


def test_r4_mismatch_of_exactly_30_percent_does_not_fire() -> None:
    req, src = MELNIKOVA
    src = replace(src, fns=Source.ok(FnsProfile({2025: D(10_000_000)}, D(0), {})))

    decision = _decide(replace(req, revenue_12m=D(13_000_000)), src)

    assert decision.reason_code != "R4_REVENUE_PROOF_REQUIRED"


@pytest.mark.parametrize(("amount", "fired"), [(10_000_000, False), (10_000_001, True)])
def test_r5_large_amount(amount: int, fired: bool) -> None:
    req = request(
        amount=amount, term=60, revenue=200_000_000, product=EQUIPMENT, purpose="equipment"
    )
    fns = FnsProfile({2024: D(190_000_000), 2025: D(200_000_000)}, D(0), {})

    decision = _decide(req, sources(fns=fns))

    assert (decision.reason_code == "R5_LARGE_AMOUNT") is fired


def _graded(points_down: str) -> tuple:  # грейды E и D подбираются через данные источников
    bad_fns = FnsProfile(
        {2024: D(40_000_000), 2025: D(24_000_000)}, D(500_000),
        {"mass_address": True, "unreliable_address": True},
    )  # fmt: skip
    if points_down == "E":  # F1 0 + F2 0 + F3 0 + F4 0 + F5 0 + F6 0
        bki = BkiReport(True, False, (BkiLoan(D(900_000), 120, 0),))
        return request(payments=900_000), sources(age=registered(0, 6), bki=bki, fns=bad_fns)
    # D: F1 20 + F2 5 + F3 12 + F4 0 + F5 0 + F6 0 = 37
    bki = BkiReport(True, False, (BkiLoan(D(0), 45, 0),))
    return request(payments=424_960), sources(bki=bki, fns=bad_fns)


def test_r6_grade_e_is_rejected() -> None:
    decision = _decide(*_graded("E"))

    assert (decision.outcome, decision.reason_code, decision.client_reason) == (
        "REJECTED", "R6_GRADE_E", "low_score",
    )  # fmt: skip


def test_r7_grade_d_goes_to_manual_review() -> None:
    decision = _decide(*_graded("D"))

    assert (decision.outcome, decision.reason_code) == ("MANUAL_REVIEW", "R7_GRADE_D")


# ── R8: грейд C ─────────────────────────────────────────────────────────────


def _grade_c(payments: int) -> tuple:
    # F1 20 + F2 15 + F3 по нагрузке + F4 0 + F5 4 + F6 3: при F3 = 12 → 54 (C)
    fns = FnsProfile({2024: D(40_000_000), 2025: D(24_000_000)}, D(50_000), {"mass_address": True})
    bki = BkiReport(True, False, (BkiLoan(D(0), 10, 0),))
    return request(payments=payments), sources(bki=bki, fns=fns)


def test_r8_counter_offer_is_half_of_requested_at_grade_c_rate() -> None:
    req, src = _grade_c(payments=424_960)
    assert score(req, src, reference_date=REF).grade == "C"

    decision = _decide(req, src)

    assert (decision.outcome, decision.reason_code) == ("COUNTER_OFFER", "R8_COUNTER_OFFER")
    offer = decision.offer
    assert offer.rate == D(22)  # база 18 + 4 п.п.
    assert offer.term_months == 12  # срок — запрошенный
    assert offer.amount <= D(1_500_000) and offer.amount % 1000 == 0
    assert offer.debt_load_pct <= 35


def test_r8_without_affordable_amount_follows_on_no_offer() -> None:
    # Платежи уже съели 35 % выручки: допустимый новый платёж ≤ 0.
    # F1 20 + F2 25 + F3 4 (нагрузка 48,75 %) + F4 0 + F5 4 + F6 3 = 56 → C.
    fns = FnsProfile({2024: D(40_000_000), 2025: D(24_000_000)}, D(50_000), {"mass_address": True})
    bki = BkiReport(True, False, (BkiLoan(D(0), 0, 0),))
    req, src = request(payments=700_000), sources(bki=bki, fns=fns)
    assert score(req, src, reference_date=REF).grade == "C"

    rejected = _decide(req, src)
    raw = load_config().model_dump(mode="python")
    raw["rules"]["R8"]["on_no_offer"] = "MANUAL_REVIEW"
    manual = _decide(req, src, config=parse_config(raw))

    assert (rejected.outcome, rejected.reason_code) == ("REJECTED", "R8_NO_OFFER")
    assert rejected.client_reason == "no_suitable_terms"
    assert (manual.outcome, manual.reason_code) == ("MANUAL_REVIEW", "R8_NO_OFFER")


# ── R9–R10: грейды A/B ──────────────────────────────────────────────────────


def test_r10_reduces_amount_when_longer_term_is_not_enough() -> None:
    # 4,5 млн при выручке 6 млн и платежах 60 тыс.: даже 24 мес дают нагрузку > 35 %.
    req = request(amount=4_500_000, revenue=6_000_000, payments=60_000)
    _, src = KOVALEV

    decision = _decide(req, src)

    offer = decision.offer
    assert decision.reason_code == "R10_COUNTER_OFFER"
    assert offer.term_months == 24 and offer.amount < D(4_500_000)
    assert offer.amount % 1000 == 0 and offer.debt_load_pct <= 35


def test_r10_tries_other_product_of_same_purpose() -> None:
    # Кассовый разрыв, 400 тыс. при выручке 430 тыс./год: в «Экспресс-обороте» не помогает
    # ни срок 24 мес, ни меньшая сумма (влезает ~251 тыс. < минимума 300 тыс.) →
    # «Овердрафт» той же цели: ~135 тыс. на 12 мес.
    req = request(amount=400_000, term=12, revenue=430_000, payments=0, purpose="cash_gap")
    fns = FnsProfile({2024: D(400_000), 2025: D(430_000)}, D(0), {})

    decision = _decide(req, sources(fns=fns, bki=BkiReport(True, False)))

    assert decision.reason_code == "R10_COUNTER_OFFER"
    offer = decision.offer
    assert offer.product.code == "OVERDRAFT"
    assert offer.term_months == 12 and offer.rate == D(20)  # грейд A: база + 0
    assert D(100_000) <= offer.amount < D(300_000) and offer.amount % 1000 == 0
    assert offer.debt_load_pct <= 35


def test_r10_does_not_switch_to_product_with_other_purpose() -> None:
    # Та же ситуация, но цель «оборотные средства»: у «Овердрафта» её нет → отказ.
    req = request(amount=400_000, term=12, revenue=430_000, payments=0, purpose="working_capital")
    fns = FnsProfile({2024: D(400_000), 2025: D(430_000)}, D(0), {})

    decision = _decide(req, sources(fns=fns, bki=BkiReport(True, False)))

    assert decision.reason_code == "R10_NO_OFFER"


def test_r10_without_any_option_is_rejected() -> None:
    req = request(amount=3_000_000, revenue=6_000_000, payments=170_000)
    fns = FnsProfile({2024: D(5_714_286), 2025: D(6_000_000)}, D(0), {})

    decision = _decide(req, sources(fns=fns, bki=BkiReport(True, False)))

    assert (decision.outcome, decision.reason_code) == ("REJECTED", "R10_NO_OFFER")
    assert decision.client_reason == "no_suitable_terms"


def test_decision_refuses_scoring_from_other_config_version() -> None:
    req, src = BAKERY
    scoring = replace(score(req, src, reference_date=REF), config_version="0.9.0")

    with pytest.raises(ValueError, match="0.9.0"):
        decide(req, src, scoring, PRODUCTS)

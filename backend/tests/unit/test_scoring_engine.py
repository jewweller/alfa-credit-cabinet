from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from engine_data import BAKERY, KOVALEV, MELNIKOVA, REF, registered, request, sources

from app.scoring.engine import full_years, score
from app.scoring.inputs import BkiLoan, BkiReport, FnsProfile, Source


def _points(result) -> dict[str, int]:  # noqa: ANN001
    return {f.id: f.points for f in result.factors}


@pytest.mark.parametrize(
    ("client", "points", "total", "grade"),
    [
        (BAKERY, {"F1": 20, "F2": 25, "F3": 20, "F4": 15, "F5": 10, "F6": 10}, 100, "A"),
        (KOVALEV, {"F1": 15, "F2": 15, "F3": 4, "F4": 15, "F5": 10, "F6": 10}, 69, "B"),
        (MELNIKOVA, {"F1": 8, "F2": 10, "F3": 20, "F4": 8, "F5": 10, "F6": 10}, 66, "B"),
    ],
    ids=["Пекарня", "Ковалёв", "Мельникова"],
)
def test_plan_examples(client, points: dict, total: int, grade: str) -> None:  # noqa: ANN001
    result = score(*client, reference_date=REF)

    assert _points(result) == points
    assert (result.total, result.grade) == (total, grade)
    assert result.config_version == "1.0.0"


def test_plan_payments_and_loads() -> None:
    bakery = score(*BAKERY, reference_date=REF)
    kovalev = score(*KOVALEV, reference_date=REF)

    assert bakery.new_payment_base_rate == D("275040.00")
    assert round(bakery.debt_load_pct, 1) == D("21.3")
    assert kovalev.new_payment_base_rate == D("183360.00")
    assert round(kovalev.debt_load_pct, 1) == D("48.7")


def test_full_years_counts_anniversaries() -> None:
    start = date(2024, 4, 10)

    assert full_years(start, date(2026, 4, 9)) == 1
    assert full_years(start, date(2026, 4, 10)) == 2


@pytest.mark.parametrize(
    ("age", "points"),
    [(registered(0, 11), 0), (registered(1), 8), (registered(2), 15), (registered(5), 15),
     (registered(6), 20)],
    ids=["11 мес", "1 год", "2 года", "5 лет", "6 лет"],
)  # fmt: skip
def test_f1_boundaries(age: date, points: int) -> None:
    result = score(request(), sources(age=age), reference_date=REF)

    assert result.factor("F1").points == points


@pytest.mark.parametrize(
    ("days", "points"), [(0, 25), (1, 15), (30, 15), (31, 5), (90, 5), (91, 0)]
)
def test_f2_boundaries(days: int, points: int) -> None:
    bki = BkiReport(True, False, (BkiLoan(D(0), days, 0), BkiLoan(D(0), 0, 0)))

    assert score(request(), sources(bki=bki), reference_date=REF).factor("F2").points == points


def test_f2_without_history() -> None:
    bki = BkiReport(False, False)

    assert score(request(), sources(bki=bki), reference_date=REF).factor("F2").points == 10


@pytest.mark.parametrize(
    ("payments", "points"),
    # Платёж 275 040 при выручке 2 млн/мес: E подобрано под нагрузку 25 / 35 / 50 %.
    [(224_960, 20), (224_961, 12), (424_960, 12), (424_961, 4), (724_960, 4), (724_961, 0)],
)
def test_f3_boundaries(payments: int, points: int) -> None:
    src = sources(bki=BkiReport(True, False))
    result = score(request(payments=payments), src, reference_date=REF)

    assert result.factor("F3").points == points


def test_f3_uses_larger_of_application_and_bki_payments() -> None:
    bki = BkiReport(True, False, (BkiLoan(D(300_000), 0, 0), BkiLoan(D(200_000), 0, 0)))

    result = score(request(payments=150_000), sources(bki=bki), reference_date=REF)

    # (500 000 + 275 040) / 2 000 000 = 38,75 %
    assert round(result.debt_load_pct, 2) == D("38.75")
    assert result.factor("F3").points == 4


def test_f3_without_revenue_gets_missing_points() -> None:
    result = score(request(revenue=0), sources(), reference_date=REF)

    assert result.factor("F3").points == 0
    assert result.debt_load_pct is None


@pytest.mark.parametrize(
    ("revenue", "points"),
    [
        ({2024: D(100), 2025: D(100)}, 15),
        ({2024: D(100), 2025: D(80)}, 8),  # −20 %
        ({2024: D(100), 2025: D("79.99")}, 0),
        ({2025: D(100)}, 8),  # нет предыдущего года
        ({2024: D(0), 2025: D(100)}, 8),  # база ≤ 0
        ({}, 8),
    ],
)
def test_f4_revenue_dynamics(revenue: dict, points: int) -> None:
    fns = FnsProfile(revenue, D(0), {})

    assert score(request(), sources(fns=fns), reference_date=REF).factor("F4").points == points


@pytest.mark.parametrize(
    ("debt", "points"), [(D(0), 10), (D("0.01"), 4), (D(100_000), 4), (D("100000.01"), 0)]
)
def test_f5_tax_debt(debt: D, points: int) -> None:
    fns = FnsProfile({2024: D(1), 2025: D(1)}, debt, {})

    assert score(request(), sources(fns=fns), reference_date=REF).factor("F5").points == points


@pytest.mark.parametrize(
    ("flags", "points"),
    [({}, 10), ({"mass_address": True}, 3),
     ({"mass_address": True, "unreliable_director": True}, 0),
     ({"mass_address": False, "unknown_flag": True}, 10)],
)  # fmt: skip
def test_f6_risk_flags(flags: dict, points: int) -> None:
    fns = FnsProfile({2024: D(1), 2025: D(1)}, D(0), flags)

    assert score(request(), sources(fns=fns), reference_date=REF).factor("F6").points == points


def test_unavailable_sources_score_zero_and_are_explained() -> None:
    base = sources()
    src = replace(
        base, registry=Source.unavailable(), fns=Source.unavailable(), bki=Source.unavailable()
    )

    result = score(request(), src, reference_date=REF)

    assert {f.id: f.points for f in result.factors if f.id != "F3"} == dict.fromkeys(
        ("F1", "F2", "F4", "F5", "F6"), 0
    )
    assert all(f.note and "unavailable" in f.note for f in result.factors if f.id != "F3")


_GROWTH = {2024: D(21_428_571), 2025: D(24_000_000)}  # F4 = 15
_DECLINE = {2024: D(40_000_000), 2025: D(24_000_000)}  # F4 = 0


@pytest.mark.parametrize(
    ("payments", "revenue", "debt", "flags", "total", "grade"),
    [
        # F1 = 20 и F2 = 25 везде; остальное подобрано под границы грейдов.
        (150_000, _GROWTH, 200_000, 2, 80, "A"),  # 20+25+20+15+0+0
        (424_960, _GROWTH, 50_000, 1, 79, "B"),  # 20+25+12+15+4+3
        (150_000, _DECLINE, 200_000, 2, 65, "B"),  # 20+25+20+0+0+0
        (424_960, _DECLINE, 50_000, 1, 64, "C"),  # 20+25+12+0+4+3
    ],
)
def test_grade_thresholds_are_inclusive(
    payments: int, revenue: dict, debt: int, flags: int, total: int, grade: str
) -> None:
    names = ("mass_address", "unreliable_address", "unreliable_director")
    fns = FnsProfile(revenue, D(debt), {name: True for name in names[:flags]})
    src = sources(bki=BkiReport(True, False), fns=fns)

    result = score(request(payments=payments), src, reference_date=REF)

    assert (result.total, result.grade) == (total, grade)


def test_result_is_reproducible() -> None:
    assert score(*BAKERY, reference_date=REF) == score(*BAKERY, reference_date=REF)

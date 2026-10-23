from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.domain.loan_math import annuity_payment

# docs/plan.md, раздел 7: (сумма, ставка %, срок мес) → платёж в рублях, как он указан в плане.
PLAN_EXAMPLES = [
    pytest.param("3000000", "18", 12, 275_040, id="Пекарня 3 млн/12 мес/18%"),
    pytest.param("2000000", "18", 12, 183_360, id="Ковалёв 2 млн/12 мес/18%"),
    pytest.param("2000000", "20", 18, 129_526, id="Ковалёв 2 млн/18 мес/20%"),
    pytest.param("2000000", "20", 24, 101_792, id="Ковалёв 2 млн/24 мес/20%"),
    pytest.param("1500000", "18", 12, 137_520, id="Мельникова 1,5 млн/12 мес/18%"),
    pytest.param("1500000", "20", 12, 138_952, id="Мельникова 1,5 млн/12 мес/20%"),
]


@pytest.mark.parametrize(("amount", "rate", "term", "plan_rub"), PLAN_EXAMPLES)
def test_matches_plan_examples_to_the_ruble(
    amount: str, rate: str, term: int, plan_rub: int
) -> None:
    payment = annuity_payment(Decimal(amount), Decimal(rate), term)

    # Округление только в тесте, чтобы сравнить с рублёвыми значениями плана; правило
    # округления в коде не фиксируется (TBD). Ни одно значение не лежит на границе .5.
    assert payment.quantize(Decimal("1"), rounding=ROUND_HALF_UP) == plan_rub


def test_result_is_not_rounded() -> None:
    payment = annuity_payment(Decimal("3000000"), Decimal("18"), 12)

    assert isinstance(payment, Decimal)
    assert payment != payment.quantize(Decimal("0.01"))
    assert abs(payment - Decimal("275039.978719")) < Decimal("0.000001")


def test_zero_rate_is_amount_divided_by_term() -> None:
    assert annuity_payment(Decimal("1200000"), Decimal("0"), 12) == Decimal("100000")


def test_single_month_returns_principal_plus_interest() -> None:
    assert annuity_payment(Decimal("100000"), Decimal("12"), 1) == Decimal("101000")


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity"])
def test_rejects_non_positive_or_non_finite_amount(amount: str) -> None:
    with pytest.raises(ValueError):
        annuity_payment(Decimal(amount), Decimal("18"), 12)


@pytest.mark.parametrize("rate", ["-0.01", "NaN", "Infinity"])
def test_rejects_negative_or_non_finite_rate(rate: str) -> None:
    with pytest.raises(ValueError):
        annuity_payment(Decimal("1000000"), Decimal(rate), 12)


@pytest.mark.parametrize("term", [0, -12])
def test_rejects_term_below_one_month(term: int) -> None:
    with pytest.raises(ValueError):
        annuity_payment(Decimal("1000000"), Decimal("18"), term)


@pytest.mark.parametrize(
    ("amount", "rate", "term"),
    [
        (1000000.0, Decimal("18"), 12),
        (Decimal("1000000"), 18.0, 12),
        (1000000, Decimal("18"), 12),
        (Decimal("1000000"), Decimal("18"), 12.0),
        (Decimal("1000000"), Decimal("18"), True),
    ],
)
def test_rejects_float_and_non_integer_inputs(amount: object, rate: object, term: object) -> None:
    with pytest.raises(TypeError):
        annuity_payment(amount, rate, term)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "mode", "step", "expected"),
    [
        ("275039.978719", "half_up", "1", "275040.00"),
        ("101791.5", "half_up", "1", "101792.00"),
        ("101791.49", "half_up", "1", "101791.00"),
        ("275039.978719", "half_up", "0.01", "275039.98"),
        ("1499999.99", "down", "1000", "1499000.00"),
        ("1500000", "down", "1000", "1500000.00"),
    ],
)
def test_round_money(value: str, mode: str, step: str, expected: str) -> None:
    from app.domain.loan_math import round_money

    assert round_money(Decimal(value), mode, Decimal(step)) == Decimal(expected)  # type: ignore[arg-type]


def test_round_money_rejects_non_positive_step() -> None:
    from app.domain.loan_math import round_money

    with pytest.raises(ValueError):
        round_money(Decimal(1), "half_up", Decimal(0))


def test_max_principal_is_inverse_of_annuity() -> None:
    from app.domain.loan_math import max_principal

    payment = annuity_payment(Decimal("2000000"), Decimal("20"), 24)

    assert abs(max_principal(payment, Decimal("20"), 24) - Decimal("2000000")) < Decimal("0.0001")
    assert max_principal(Decimal("100000"), Decimal("0"), 12) == Decimal("1200000")
    assert max_principal(Decimal("-1"), Decimal("18"), 12) == 0


def _schedule(amount: str, rate: str, term: int, payment: str):  # noqa: ANN202
    from app.domain.loan_math import annuity_schedule

    return annuity_schedule(
        Decimal(amount), Decimal(rate), term, Decimal(payment), Decimal("0.01"), "half_up"
    )


@pytest.mark.parametrize(
    ("amount", "rate", "term", "payment"),
    [
        ("3000000", "18", 12, "275040"),  # Пекарня, план, раздел 7
        ("2000000", "20", 24, "101792"),  # Ковалёв
        ("3000000", "18", 12, "275039.98"),  # тот же платёж до копеек (вопрос K1)
        ("1200000", "0", 12, "100000"),
    ],
)
def test_schedule_repays_exactly_the_principal(
    amount: str, rate: str, term: int, payment: str
) -> None:
    rows = _schedule(amount, rate, term, payment)

    assert [r.number for r in rows] == list(range(1, term + 1))
    assert sum(r.principal for r in rows) == Decimal(amount)
    assert rows[-1].balance == 0
    assert all(r.payment == r.principal + r.interest for r in rows)
    assert all(r.payment == Decimal(payment) for r in rows[:-1])
    assert all(r.interest == r.interest.quantize(Decimal("0.01")) for r in rows)
    balances = [r.balance for r in rows]
    assert balances == sorted(balances, reverse=True)


def test_schedule_first_interest_and_last_payment() -> None:
    rows = _schedule("3000000", "18", 12, "275040")

    assert rows[0].interest == Decimal("45000.00")  # 3 000 000 × 18 % / 12
    # Платёж округлён до рубля вверх — последний платёж чуть меньше и закрывает остаток.
    assert Decimal("275000") < rows[-1].payment < Decimal("275040")


def test_schedule_rejects_payment_below_interest() -> None:
    with pytest.raises(ValueError, match="не покрывает"):
        _schedule("3000000", "18", 12, "40000")


@pytest.mark.parametrize(
    "bad", [("0", "18", 12, "1"), ("1000", "18", 0, "1"), ("1000", "18", 12, "0")]
)
def test_schedule_rejects_non_positive_inputs(bad: tuple) -> None:
    with pytest.raises(ValueError):
        _schedule(*bad)

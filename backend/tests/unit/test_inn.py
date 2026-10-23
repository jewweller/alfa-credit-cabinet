import pytest

from app.domain.inn import is_valid_inn

# Все тестовые ИНН из docs/plan.md, раздел 8: «Все ИНН проходят проверку контрольной суммы».
PLAN_INNS = [
    "7701000019",  # ООО «Пекарня Север»
    "500100001072",  # ИП Ковалёв А.С.
    "500100002020",  # ИП Мельникова Е.В.
    "7701000026",  # ООО «СтройРесурс»
    "7701000033",  # ООО «Вектор»
    "7701000058",  # ООО «Мираж»
    "7701000065",  # ООО «Сбой-Тест»
    "7701000072",  # нет в реестре — но контрольная сумма верная
]


@pytest.mark.parametrize("inn", PLAN_INNS)
def test_plan_inns_are_valid(inn: str) -> None:
    assert is_valid_inn(inn)


@pytest.mark.parametrize("inn", PLAN_INNS)
def test_changed_last_digit_is_invalid(inn: str) -> None:
    broken = inn[:-1] + str((int(inn[-1]) + 1) % 10)

    assert not is_valid_inn(broken)


def test_12_digit_inn_checks_both_control_digits() -> None:
    valid = "500100001072"
    wrong_first_control = valid[:10] + "8" + valid[11]
    wrong_second_control = valid[:11] + "3"

    assert not is_valid_inn(wrong_first_control)
    assert not is_valid_inn(wrong_second_control)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "770100001",  # 9 цифр
        "77010000190",  # 11 цифр
        "7701000019000",  # 13 цифр
        " 7701000019",
        "7701000019 ",
        "770100001a",
        "７７０１００００１９",  # полноширинные цифры Unicode
    ],
)
def test_malformed_values_are_invalid(value: str) -> None:
    assert not is_valid_inn(value)

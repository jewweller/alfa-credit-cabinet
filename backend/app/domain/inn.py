"""Проверка контрольной суммы ИНН (план, раздел 4, этап 2: «ИНН с верной контрольной суммой»).

Алгоритм ФНС: 10 цифр — ИНН юрлица (одна контрольная цифра), 12 цифр — ИНН физлица / ИП
(две контрольные цифры). Контрольная цифра = (сумма цифр × веса) mod 11 mod 10.
"""

import re

_INN_RE = re.compile(r"[0-9]{10}|[0-9]{12}")

_WEIGHTS_10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_WEIGHTS_12_FIRST = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_WEIGHTS_12_SECOND = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _check_digit(digits: list[int], weights: tuple[int, ...]) -> int:
    return sum(d * w for d, w in zip(digits, weights, strict=False)) % 11 % 10


def is_valid_inn(value: str) -> bool:
    """True, если строка — ИНН из 10 или 12 цифр ASCII с верными контрольными цифрами."""
    if not _INN_RE.fullmatch(value):
        return False
    digits = [int(c) for c in value]
    if len(digits) == 10:
        return _check_digit(digits, _WEIGHTS_10) == digits[9]
    return (
        _check_digit(digits, _WEIGHTS_12_FIRST) == digits[10]
        and _check_digit(digits, _WEIGHTS_12_SECOND) == digits[11]
    )

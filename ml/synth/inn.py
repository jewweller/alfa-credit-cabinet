"""Checksums compatible with backend/app/domain/inn.py at 35ab47d."""

import re

WEIGHTS = (
    (2, 4, 10, 3, 5, 9, 4, 6, 8),
    (7, 2, 4, 10, 3, 5, 9, 4, 6, 8),
    (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8),
)


def digit(prefix: str, weights: tuple[int, ...]) -> str:
    return str(sum(int(c) * w for c, w in zip(prefix, weights, strict=True)) % 11 % 10)


def valid_inn(value: str) -> bool:
    if not re.fullmatch(r"[0-9]{10}|[0-9]{12}", value):
        return False
    if len(value) == 10:
        return digit(value[:9], WEIGHTS[0]) == value[9]
    return digit(value[:10], WEIGHTS[1]) == value[10] and digit(value[:11], WEIGHTS[2]) == value[11]


def unique_inn(fake, kind: str, used: set[str]) -> str:
    for _ in range(10000):
        value = fake.businesses_inn() if kind == "LLC" else fake.individuals_inn()
        if value not in used and valid_inn(value):
            used.add(value)
            return value
    raise RuntimeError("unable to generate a unique INN")

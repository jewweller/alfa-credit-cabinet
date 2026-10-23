"""Тестовые данные движков. Числа клиентов — из docs/plan.md, раздел 7 (Пекарня, Ковалёв,
Мельникова) и раздел 8. Это входы тестов, а не фикстуры моков."""

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

from app.scoring.inputs import (
    ApplicantSources,
    BkiLoan,
    BkiReport,
    FnsProfile,
    LoanRequest,
    ProductTerms,
    RegistryData,
    Source,
)

REF = date(2026, 10, 23)

# Продукты — как в seed/products.json (план, раздел 7).
EXPRESS = ProductTerms(
    "p1", "EXPRESS_WC", "Экспресс-оборот", ("working_capital", "cash_gap"),
    D(300_000), D(5_000_000), 3, 24, D(18),
)  # fmt: skip
EQUIPMENT = ProductTerms(
    "p2", "EQUIPMENT", "Инвест-оборудование", ("equipment",),
    D(1_000_000), D(30_000_000), 12, 60, D(16),
)  # fmt: skip
OVERDRAFT = ProductTerms(
    "p3", "OVERDRAFT", "Овердрафт для бизнеса", ("cash_gap",),
    D(100_000), D(3_000_000), 12, 12, D(20),
)  # fmt: skip
PRODUCTS = (EXPRESS, EQUIPMENT, OVERDRAFT)


def registered(years: int, months: int = 0) -> date:
    month = REF.month - months
    year = REF.year - years
    if month <= 0:
        month += 12
        year -= 1
    return date(year, month, REF.day)


def request(
    amount: int = 3_000_000,
    term: int = 12,
    revenue: int = 24_000_000,
    payments: int | str = 150_000,
    product: ProductTerms = EXPRESS,
    purpose: str = "working_capital",
) -> LoanRequest:
    return LoanRequest(product, D(amount), term, purpose, D(revenue), D(payments))


def sources(
    kind: str = "LLC",
    status: str = "ACTIVE",
    age: date | None = None,
    bki: BkiReport | None = None,
    fns: FnsProfile | None = None,
) -> ApplicantSources:
    return ApplicantSources(
        kind,  # type: ignore[arg-type]
        Source.ok(RegistryData(status, age or registered(7))),
        Source.ok(fns or FnsProfile({2024: D(21_428_571), 2025: D(24_000_000)}, D(0), {})),
        Source.ok(bki or BkiReport(True, False, (BkiLoan(D(150_000), 0, 0),))),
    )


# Клиент 1. ООО «Пекарня Север»: 7 лет, без просрочек, выручка 24 млн (+12%), платежи 150 тыс.
BAKERY = (request(), sources())

# Клиент 2. ИП Ковалёв: 3 года, просрочка до 30 дней, выручка 6 млн (+5%), платежи 60 тыс.
KOVALEV = (
    request(amount=2_000_000, revenue=6_000_000, payments=60_000),
    sources(
        kind="IE",
        age=registered(3),
        bki=BkiReport(True, False, (BkiLoan(D(60_000), 20, 0),)),
        fns=FnsProfile({2024: D(5_714_286), 2025: D(6_000_000)}, D(0), {}),
    ),
)

# Клиент 3. ИП Мельникова: 1,5 года, нет КИ, анкета 12 млн, ФНС 7 млн, платежей нет.
MELNIKOVA = (
    request(amount=1_500_000, revenue=12_000_000, payments=0),
    sources(
        kind="IE",
        age=registered(1, 6),
        bki=BkiReport(False, False),
        fns=FnsProfile({2025: D(7_000_000)}, D(0), {}),
    ),
)


def with_registry(src: ApplicantSources, registry: Source) -> ApplicantSources:
    return replace(src, registry=registry)

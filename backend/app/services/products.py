"""Каталог и подбор продукта (план, раздел 4, этап 0; экран C3).

Подбор — правила, без ИИ: продукты с нужной целью, сумма и срок приведены к лимитам
продукта, платёж — аннуитет по базовой ставке с округлением из config.yaml. Сначала
продукты, подходящие без изменений, затем с меньшим платежом; не больше трёх.
Так же считают моки фронта (frontend/src/mocks/recommend.ts).

Модель ML здесь не вызывается: по docs/ml-ranking.md и docs/ml-howto.md `ml.rank_products`
остаётся заглушкой — кандидатов 1–3, переставлять почти нечего. Этот порядок и есть
«порядок бэкенда без модели» из docs/ml-ranking.md.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.models import Product as ProductRow
from app.schemas.common import ErrorCode
from app.schemas.products import (
    Product,
    ProductRecommendation,
    ProductRecommendRequest,
    RecommendationAdjustment,
)
from app.scoring.config import EngineConfig, load_config
from app.scoring.finance import monthly_payment

MAX_RECOMMENDATIONS = 3


def to_product(row: ProductRow) -> Product:
    return Product(
        id=row.id,
        code=row.code,
        name=row.name,
        purpose_tags=row.purpose_tags,
        min_amount=row.min_amount,
        max_amount=row.max_amount,
        min_term=row.min_term,
        max_term=row.max_term,
        base_rate=row.base_rate,
    )


def catalog(session: Session) -> list[ProductRow]:
    return list(session.scalars(select(ProductRow).order_by(ProductRow.code)))


def _clamp[T: (int, Decimal)](value: T, low: T, high: T) -> T:
    return min(high, max(low, value))


def recommend(
    session: Session, body: ProductRecommendRequest, config: EngineConfig | None = None
) -> list[ProductRecommendation]:
    if body.amount <= 0:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Сумма должна быть больше нуля", "amount")
    config = config or load_config()

    found = []
    for row in catalog(session):
        if body.purpose not in row.purpose_tags:
            continue
        amount = _clamp(body.amount, row.min_amount, row.max_amount)
        term = _clamp(body.term_months, row.min_term, row.max_term)
        adjusted = []
        if amount != body.amount:
            adjusted.append(RecommendationAdjustment.AMOUNT)
        if term != body.term_months:
            adjusted.append(RecommendationAdjustment.TERM_MONTHS)
        found.append(
            ProductRecommendation(
                product=to_product(row),
                amount=amount,
                term_months=term,
                rate=row.base_rate,
                monthly_payment=monthly_payment(config, amount, row.base_rate, term),
                adjusted=adjusted,
            )
        )
    # sorted устойчив: при равенстве остаётся порядок каталога (по коду продукта).
    found.sort(key=lambda r: (len(r.adjusted), r.monthly_payment))
    return found[:MAX_RECOMMENDATIONS]

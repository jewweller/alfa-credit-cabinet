"""Ранжирование ленты логистической регрессией (docs/ml-ranking.md, docs/ml-experiment.md).

Только стандартная библиотека: модель — 20 коэффициентов и свободный член в
`ml/models/feed_logreg.json`, обученные `ml/synth/logreg.py` на синтетике.

Оценка новости: z = b + Σ wⱼ·xⱼ по признакам `features()`, score = σ(z). Порядок — по z, при
равенстве по id. Причины показа — совпавшие теги новости с наибольшим положительным вкладом
wⱼ·xⱼ в z (не больше двух). Вклад линейной модели считается точно, поэтому причина — честное
«почему модель подняла новость». Нет такого тега — причин нет, бэкенд покажет причины правил.

`rank_products` — заглушка: кандидатов 1–3, ранжировать нечего (docs/ml-howto.md).
"""

import json
import math
from functools import lru_cache
from pathlib import Path

from .features import FEATURE_VERSION, FEATURES, features

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "feed_logreg.json"
MAX_REASONS = 2

# Признак совпадения тега → код причины (FeedReasonCode в backend/app/schemas/feed.py).
REASON_FEATURES = {
    "m_okved": "okved",
    "m_status": "status",
    "m_product": "product",
    "m_segment": "segment",
}
SEGMENT_TEXT = {"micro": "Подобрано для микробизнеса", "small": "Подобрано для малого бизнеса"}


@lru_cache(maxsize=1)
def _model() -> tuple[str, float, tuple[float, ...]]:
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if model["features"] != FEATURES or model["feature_version"] != FEATURE_VERSION:
        raise RuntimeError("Признаки модели не совпадают с features(); переобучите модель")
    version = str(model["model_version"]).strip()
    coef = tuple(float(c) for c in model["coef"])
    intercept = float(model["intercept"])
    if not version or len(coef) != len(FEATURES):
        raise RuntimeError("Файл модели повреждён")
    if not all(math.isfinite(v) for v in (*coef, intercept)):
        raise RuntimeError("В модели нечисловые коэффициенты")
    return version, intercept, coef


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


def _reason_text(code: str, profile: dict) -> str:
    """Короткий текст без персональных данных: только ОКВЭД и сегмент компании."""
    if code == "okved":
        return f"Новость вашей отрасли (ОКВЭД {profile['okved_main']})"
    if code == "segment":
        return SEGMENT_TEXT[profile["segment"]]
    if code == "status":
        return "Подсказка к текущему этапу вашей заявки"
    return "Связано с продуктом из вашей заявки"


def _reasons(x: list[float], coef: tuple[float, ...], candidate: dict, profile: dict) -> list:
    matched = set(candidate["matched"])
    contributions = []
    for name, code in REASON_FEATURES.items():
        j = FEATURES.index(name)
        contribution = coef[j] * x[j]
        if contribution > 0 and code in matched:
            contributions.append((contribution, code))
    contributions.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"code": code, "text": _reason_text(code, profile)}
        for _, code in contributions[:MAX_REASONS]
    ]


def rank_feed(payload: dict) -> dict:
    """FeedRankRequest → FeedRankResponse: те же кандидаты, каждый один раз, лучший первым."""
    version, intercept, coef = _model()
    try:
        profile, candidates, now = payload["profile"], payload["candidates"], payload["now"]
        ids = [str(c["id"]) for c in candidates]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Запрос не по схеме FeedRankRequest: {error!r}") from error
    if len(ids) != len(set(ids)):
        raise ValueError("Кандидаты повторяются")

    scored = []
    for candidate, cid in zip(candidates, ids, strict=True):
        try:
            x = features(profile, candidate, now)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Не удалось посчитать признаки новости {cid}: {error!r}") from error
        z = intercept + sum(w * v for w, v in zip(coef, x, strict=True))
        if not math.isfinite(z):
            raise ValueError(f"Нечисловая оценка новости {cid}")
        scored.append((z, cid, _reasons(x, coef, candidate, profile)))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return {
        "model_version": version,
        "ranking": [
            {"id": cid, "score": _sigmoid(z), "reasons": reasons} for z, cid, reasons in scored
        ],
    }


def rank_products(payload: dict) -> dict:
    """Порядок бэкенда без изменений: на подборе кредита модель не используется."""
    ids = [str(c["product"]["id"]) for c in payload["candidates"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Кандидаты повторяются")
    count = len(ids)
    return {
        "model_version": "product-stub-0.1.0",
        "ranking": [
            {"product_id": pid, "score": (count - n) / count, "reasons": []}
            for n, pid in enumerate(ids)
        ],
    }

# ML: как сделать ранжирование ленты — пошагово

Инструкция для ML-команды. Что модель получает и что возвращает, описано в [`ml-ranking.md`](ml-ranking.md). Здесь — **как это сделать**: от данных до PR. Весь код ниже проверен: он запускается на нашем репозитории, ответы проходят схемы бэкенда.

**Срок: PR в `main` до воскресенья 25.10, 18:00.** В понедельник в 14:00 заморозка, бэкенду нужно время подключить модель.

## Что нужно получить

Функцию `rank_feed(payload: dict) -> dict` в `ml/synth/ranking.py`, которая:

- получает клиента и 2–15 новостей, уже отобранных бэкендом;
- возвращает **все** эти новости, лучшую первой, у каждой `score` от 0 до 1;
- отвечает быстрее 1 секунды, не ходит в сеть и БД;
- по качеству **лучше правил** (`rule_score`) — и это показано цифрой в README.

`rank_products` оставляем заглушкой: кандидатов 1–3, ранжировать там нечего.

## Идея в двух абзацах

Реальных кликов у нас нет и не будет: по условиям кейса только синтетические данные. Поэтому делаем так, как делают при отсутствии данных: **записываем гипотезы о поведении клиентов** («подсказка к шагу важна, когда от клиента ждут действия», «меры поддержки интересны микробизнесу и молодым компаниям», «свежее интереснее»), **генерируем по ним клики** и обучаем модель **только на кликах**. Модель гипотез не видит — она должна восстановить их сама.

Правила бэкенда — простая сумма совпадений тегов. Они не умеют учитывать сочетания (статус × тема, сегмент × тема, рост выручки × оборудование) и считают свежесть слишком слабо. Модель это умеет, поэтому на отложенных клиентах выигрывает у правил. Честно пишем в README: модель выучила наши гипотезы, а не настоящих клиентов; на проде те же шаги повторяются на реальных кликах.

## Как устроена папка `ml`

```
ml/
  __init__.py              # уже есть: экспортирует rank_feed, rank_products
  synth/
    make_requests.py       # шаг 1 — запросы, как их пришлёт бэкенд
    simulate.py            # шаг 2 — синтетические клики
    features.py            # признаки; общие для обучения и rank_feed
    train.py               # шаг 3 — обучение, сравнение с правилами, веса
    ranking.py             # шаг 5 — rank_feed для бэкенда
  models/feed_ranker.json  # веса модели, коммитим (меньше 1 КБ)
  data/                    # сгенерированные данные, НЕ коммитим (~11 МБ)
  tests/test_ranking.py    # шаг 4
  README.md                # шаг 6 — результаты
```

Добавьте `ml/data/` в `.gitignore`.

## Шаг 0. Окружение

```bash
cd ml
uv venv --python 3.12
uv pip install numpy scikit-learn pytest
```

sklearn нужен **только для обучения**. `rank_feed` работает на стандартной библиотеке Python: веса — это JSON, бэкенду ничего ставить не нужно.

## Шаг 1. Запросы — `ml/synth/make_requests.py`

Генерируем 3000 случайных клиентов (отрасль, сегмент, возраст компании, выручка, 0–2 заявки в разных статусах). Новости для каждого отбирает **код бэкенда**, запрос проверяет **схема бэкенда** — так данные гарантированно совпадают с тем, что придёт в `rank_feed`.

```python
"""Шаг 1. Синтетические запросы ранжирования ленты — ровно такие, какие пришлёт бэкенд.

Кандидатов отбирает код бэкенда (app.domain.feed_ranking), запрос проверяет его же схема
(app.schemas.ml.FeedRankRequest), поэтому данные заведомо совпадают с контрактом.

Запуск из папки backend/ (нужно окружение бэкенда):
    PYTHONPATH=. uv run python ../ml/synth/make_requests.py --n 3000 --out ../ml/data/requests.jsonl
"""

import argparse
import json
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.domain.feed_ranking import OKVED_NAMES, FeedProfile, eligible_news
from app.domain.state_machine import ApplicationStatus as S
from app.schemas.companies import CompanyKind, CompanySegment
from app.schemas.feed import NewsItem
from app.schemas.ml import FeedRankCandidate, FeedRankRequest, RankerApplication, RankerProfile
from app.schemas.products import LoanPurpose

SEED = get_settings().seed_dir
NEWS = [NewsItem.model_validate(n) for n in json.loads((SEED / "news.json").read_text())]
PRODUCTS = {p["code"]: p["name"] for p in json.loads((SEED / "products.json").read_text())}
PURPOSE = {
    "EXPRESS_WC": LoanPurpose.WORKING_CAPITAL,
    "EQUIPMENT": LoanPurpose.EQUIPMENT,
    "OVERDRAFT": LoanPurpose.CASH_GAP,
}
STATUSES = [s for s in S if s != S.CANCELLED]
REGIONS = ["Москва", "Московская область", "Санкт-Петербург", "Казань", "Екатеринбург"]


def random_profile(rng: random.Random) -> RankerProfile:
    registered = date(2010, 1, 1) + timedelta(days=rng.randint(0, 16 * 365))
    revenue = {}
    if rng.random() < 0.85:  # у части компаний ФНС не вернул выручку
        base = rng.lognormvariate(16.5, 1.0)  # ~15 млн ₽ в среднем
        revenue = {"2024": int(base), "2025": int(base * rng.uniform(0.7, 1.5))}
    apps = []
    for _ in range(rng.choice([0, 1, 1, 1, 2])):
        code = rng.choice(list(PRODUCTS))
        apps.append(
            RankerApplication(status=rng.choice(STATUSES), product_code=code, purpose=PURPOSE[code])
        )
    return RankerProfile(
        kind=rng.choice(list(CompanyKind)),
        okved_main=rng.choice(list(OKVED_NAMES)),
        region=rng.choice(REGIONS),
        segment=rng.choice(list(CompanySegment)),
        registered_at=registered,
        revenue=revenue,
        applications=apps,
    )


def make_request(rng: random.Random) -> FeedRankRequest | None:
    profile = random_profile(rng)
    now = datetime(2026, 10, 20, tzinfo=UTC) + timedelta(hours=rng.randint(0, 30 * 24))
    feed_profile = FeedProfile(
        okved_main=profile.okved_main,
        segment=profile.segment,
        products={a.product_code: PRODUCTS[a.product_code] for a in profile.applications},
        statuses=frozenset(a.status for a in profile.applications),
    )
    ranked = eligible_news(NEWS, feed_profile, now)
    if len(ranked) < 2:  # ранжировать нечего
        return None
    candidates = [
        FeedRankCandidate(
            **r.news.model_dump(), rule_score=r.score, matched=[x.code for x in r.reasons]
        )
        for r in ranked
    ]
    return FeedRankRequest(now=now, profile=profile, candidates=candidates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.out.open("w") as f:
        while written < args.n:
            request = make_request(rng)
            if request:
                f.write(request.model_dump_json() + "\n")
                written += 1
    print(f"{written} запросов → {args.out}")


if __name__ == "__main__":
    main()
```

Запуск — из папки `backend/`, в окружении бэкенда:

```bash
cd backend
PYTHONPATH=. uv run python ../ml/synth/make_requests.py --n 3000 --out ../ml/data/requests.jsonl
# 3000 запросов → ../ml/data/requests.jsonl
```

## Шаг 2. Клики — `ml/synth/simulate.py`

Функция `interest` — это ваши гипотезы. Каждая строка — одна гипотеза с комментарием. **Это главное место, где нужна ваша голова:** можно менять, добавлять, спорить. Всё, что здесь записано, перенесите в README.

```python
"""Шаг 2. Синтетические клики: как вели бы себя клиенты, если бы ленту показывали всем.

Реальных данных нет и не будет (условия кейса), поэтому поведение задаём гипотезами —
они записаны ниже и в README. Модель потом должна восстановить их по одним кликам.

Запуск из папки ml/:
    .venv/bin/python -m synth.simulate --requests data/requests.jsonl --out data/clicks.csv
"""

import argparse
import csv
import json
import math
import random
from pathlib import Path

from synth.features import ACTION_STATUSES, revenue_growth


def interest(profile: dict, candidate: dict, now: str) -> float:
    """Скрытая заинтересованность (логит). Модель её не видит — только клики."""
    from datetime import date, datetime

    matched = set(candidate["matched"])
    topic = candidate["topic"]
    apps = profile["applications"]
    days = (
        datetime.fromisoformat(now) - datetime.fromisoformat(candidate["published_at"])
    ).total_seconds() / 86400
    age = (
        datetime.fromisoformat(now).date() - date.fromisoformat(profile["registered_at"])
    ).days / 365
    action = any(a["status"] in ACTION_STATUSES for a in apps)

    z = -2.2
    z += 1.2 * ("okved" in matched)  # своя отрасль интересна
    z += 0.8 * ("status" in matched)  # подсказка к своему шагу…
    z += 1.4 * (topic == "step" and action)  # …особенно когда от клиента ждут действия
    z += 0.5 * ("product" in matched)
    z += 1.0 * (
        topic == "support" and (profile["segment"] == "micro" or age < 2)
    )  # меры поддержки — малым и молодым
    z -= 0.4 * (topic == "support" and profile["segment"] == "small" and age >= 2)
    z += 0.9 * (topic == "product" and not apps)  # ещё не выбрал продукт — изучает условия
    z += 1.5 * math.exp(-max(0.0, days) / 7)  # свежее интереснее, за неделю — втрое слабее
    growth = revenue_growth(profile["revenue"])
    z += (
        1.2 * ("EQUIPMENT" in candidate["tags"].get("product", [])) * max(0.0, growth)
    )  # растут — думают об оборудовании
    return z


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    rows = 0
    with args.requests.open() as src, args.out.open("w", newline="") as dst:
        writer = csv.writer(dst)
        writer.writerow(["request", "news_id", "p_click", "click"])
        for i, line in enumerate(src):
            request = json.loads(line)
            for c in request["candidates"]:
                z = interest(request["profile"], c, request["now"]) + rng.gauss(
                    0, 0.5
                )  # шум: люди непредсказуемы
                p = 1 / (1 + math.exp(-z))
                writer.writerow([i, c["id"], round(p, 4), int(rng.random() < p)])
                rows += 1
    print(f"{rows} показов → {args.out}")


if __name__ == "__main__":
    main()
```

```bash
cd ml
.venv/bin/python -m synth.simulate --requests data/requests.jsonl --out data/clicks.csv
# 16869 показов → data/clicks.csv
```

## Шаг 3. Признаки и обучение

### `ml/synth/features.py`

Признаки пары «клиент × новость». Один файл для обучения и для `rank_feed` — чтобы модель на проде видела ровно то же, что при обучении.

```python
"""Признаки пары «клиент × новость». Один и тот же код — в обучении и в rank_feed.

Только стандартная библиотека: бэкенду не нужно ставить sklearn ради ранжирования.
"""

import math
from datetime import date, datetime

# Статусы, в которых клиенту нужно что-то сделать.
ACTION_STATUSES = {"INFO_REQUESTED", "APPROVED", "COUNTER_OFFER", "SIGNING"}

FEATURES = [
    "m_okved",
    "m_status",
    "m_product",
    "m_segment",
    "m_general",
    "topic_product",
    "topic_industry",
    "topic_step",
    "topic_support",
    "fresh_7d",
    "micro",
    "young",
    "no_apps",
    "action_needed",
    "product_known",
    "growth",
    # Пересечения: логистической регрессии их нужно дать явно.
    "step_x_action",
    "support_x_small_or_young",
    "product_topic_x_no_apps",
    "equipment_x_growth",
]


def _dt(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def _date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def revenue_growth(revenue: dict[str, int]) -> float:
    """Рост выручки за последний год, от −1 до 1; нет данных — 0."""
    years = sorted(revenue)
    if len(years) < 2 or not revenue[years[-2]]:
        return 0.0
    return max(-1.0, min(1.0, revenue[years[-1]] / revenue[years[-2]] - 1))


def features(profile: dict, candidate: dict, now: str | datetime) -> list[float]:
    now = _dt(now)
    matched = set(candidate["matched"])
    topic = candidate["topic"]
    apps = profile["applications"]
    days = max(0.0, (now - _dt(candidate["published_at"])).total_seconds() / 86400)
    age_years = (now.date() - _date(profile["registered_at"])).days / 365
    micro = profile["segment"] == "micro"
    young = age_years < 2
    no_apps = not apps
    action = any(a["status"] in ACTION_STATUSES for a in apps)
    known = bool(set(candidate["tags"].get("product", [])) & {a["product_code"] for a in apps})
    growth = revenue_growth(profile["revenue"])
    values = {
        "m_okved": "okved" in matched,
        "m_status": "status" in matched,
        "m_product": "product" in matched,
        "m_segment": "segment" in matched,
        "m_general": "general" in matched,
        "topic_product": topic == "product",
        "topic_industry": topic == "industry",
        "topic_step": topic == "step",
        "topic_support": topic == "support",
        "fresh_7d": math.exp(-days / 7),
        "micro": micro,
        "young": young,
        "no_apps": no_apps,
        "action_needed": action,
        "product_known": known,
        "growth": growth,
        "step_x_action": topic == "step" and action,
        "support_x_small_or_young": topic == "support" and (micro or young),
        "product_topic_x_no_apps": topic == "product" and no_apps,
        "equipment_x_growth": ("EQUIPMENT" in candidate["tags"].get("product", []))
        * max(0.0, growth),
    }
    return [float(values[name]) for name in FEATURES]
```

### `ml/synth/train.py`

Логистическая регрессия: простая, быстрая, и её веса можно прочитать — это важно для защиты («почему модель подняла эту новость»). Делим **по клиентам**: 80 % на обучение, 20 % на проверку. Сравниваем по **NDCG@5** — насколько хорошо первые 5 новостей совпадают с идеальным порядком.

```python
"""Шаг 3. Обучение и проверка: логистическая регрессия на кликах, сравнение с правилами.

Запуск из папки ml/:
    .venv/bin/python -m synth.train --requests data/requests.jsonl --clicks data/clicks.csv
Пишет веса в models/feed_ranker.json и печатает NDCG@5: модель, правила, случайный порядок.
"""

import argparse
import csv
import json
import random
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from synth.features import FEATURES, features

VERSION = "feed-ranker-0.1.0"


def ndcg_at_k(relevance_in_order: list[float], k: int = 5) -> float:
    def dcg(values: list[float]) -> float:
        return sum(v / np.log2(i + 2) for i, v in enumerate(values[:k]))

    ideal = dcg(sorted(relevance_in_order, reverse=True))
    return dcg(relevance_in_order) / ideal if ideal else 1.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--clicks", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("models/feed_ranker.json"))
    args = parser.parse_args()

    requests = [json.loads(line) for line in args.requests.open()]
    clicks = {
        (int(r["request"]), r["news_id"]): (float(r["p_click"]), int(r["click"]))
        for r in csv.DictReader(args.clicks.open())
    }

    # Делим по клиентам, а не по строкам: проверяем на тех, кого модель не видела.
    ids = list(range(len(requests)))
    random.Random(0).shuffle(ids)
    test_ids = set(ids[: len(ids) // 5])

    X, y = [], []
    for i, req in enumerate(requests):
        if i in test_ids:
            continue
        for c in req["candidates"]:
            X.append(features(req["profile"], c, req["now"]))
            y.append(clicks[(i, c["id"])][1])
    model = LogisticRegression(C=1.0, max_iter=2000).fit(np.array(X), np.array(y))

    # Оценка: релевантность — истинная вероятность клика из симулятора (на синтетике она известна).
    scores = {"модель": [], "правила (rule_score)": [], "случайно": []}
    rng = random.Random(1)
    for i in test_ids:
        req = requests[i]
        cands = req["candidates"]
        rel = {c["id"]: clicks[(i, c["id"])][0] for c in cands}
        logits = model.decision_function(
            np.array([features(req["profile"], c, req["now"]) for c in cands])
        )
        orders = {
            "модель": [
                c["id"] for _, c in sorted(zip(logits, cands, strict=True), key=lambda t: -t[0])
            ],
            "правила (rule_score)": [
                c["id"] for c in sorted(cands, key=lambda c: -c["rule_score"])
            ],
            "случайно": rng.sample([c["id"] for c in cands], len(cands)),
        }
        for name, order in orders.items():
            scores[name].append(ndcg_at_k([rel[x] for x in order]))
    for name, values in scores.items():
        print(f"NDCG@5 {name:22s} {np.mean(values):.3f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    weights = {
        "model_version": VERSION,
        "features": FEATURES,
        "coef": [round(float(w), 4) for w in model.coef_[0]],
        "intercept": round(float(model.intercept_[0]), 4),
    }
    args.out.write_text(json.dumps(weights, ensure_ascii=False, indent=2) + "\n")
    print(f"веса → {args.out}")
    for name, w in sorted(zip(FEATURES, weights["coef"], strict=True), key=lambda t: -abs(t[1])):
        print(f"  {name:26s} {w:+.2f}")


if __name__ == "__main__":
    main()
```

```bash
.venv/bin/python -m synth.train --requests data/requests.jsonl --clicks data/clicks.csv
```

Что получилось у нас (seed 42 / 7):

```
NDCG@5 модель                 0.962
NDCG@5 правила (rule_score)   0.915
NDCG@5 случайно               0.812
```

Самые большие веса — `equipment_x_growth`, `step_x_action`, `fresh_7d`, `support_x_small_or_young`: модель нашла ровно те сочетания, которых нет в правилах.

## Шаг 4. Тесты — `ml/tests/test_ranking.py`

Проверяют то, за что бэкенд отбросит ответ: все кандидаты на месте, `score` в 0…1, причины не длиннее 120 символов, ответ одинаковый при повторе, скорость.

```python
"""Шаг 4. Проверки контракта: запускать из папки ml/ — .venv/bin/python -m pytest -q"""

import json
import time
from pathlib import Path

from synth.ranking import rank_feed

EXAMPLE = Path(__file__).resolve().parents[2] / "docs" / "ml" / "feed-rank.request.json"


def _request() -> dict:
    return json.loads(EXAMPLE.read_text())


def test_returns_every_candidate_once() -> None:
    req = _request()
    ranked = [item["id"] for item in rank_feed(req)["ranking"]]
    assert sorted(ranked) == sorted(c["id"] for c in req["candidates"])


def test_scores_between_0_and_1_and_sorted() -> None:
    scores = [item["score"] for item in rank_feed(_request())["ranking"]]
    assert all(0 <= s <= 1 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_reasons_fit_contract() -> None:
    for item in rank_feed(_request())["ranking"]:
        assert len(item["reasons"]) <= 2
        assert all(len(r["text"]) <= 120 for r in item["reasons"])


def test_deterministic() -> None:
    assert rank_feed(_request()) == rank_feed(_request())


def test_fast_enough() -> None:
    req = _request()
    start = time.perf_counter()
    for _ in range(100):
        rank_feed(req)
    assert (time.perf_counter() - start) / 100 < 0.05  # бэкенд ждёт не больше 1 с
```

```bash
.venv/bin/python -m pytest -q
# 5 passed
```

## Шаг 5. `ml/synth/ranking.py` — то, что вызывает бэкенд

Заменяет текущую заглушку. Веса читаются один раз при импорте.

```python
"""Ранжирование для бэкенда: JSON → JSON (docs/ml-ranking.md). Только стандартная библиотека."""

import json
import math
from pathlib import Path

from .features import FEATURES, features

_WEIGHTS = json.loads(
    (Path(__file__).resolve().parent.parent / "models" / "feed_ranker.json").read_text()
)
if _WEIGHTS["features"] != FEATURES:
    raise RuntimeError("models/feed_ranker.json обучен на другом наборе признаков — переобучите")


def rank_feed(payload: dict) -> dict:
    """Все кандидаты, лучший первым; score — вероятность клика по модели (0…1)."""
    profile, now = payload["profile"], payload["now"]
    scored = []
    for c in payload["candidates"]:
        z = _WEIGHTS["intercept"] + sum(
            w * x for w, x in zip(_WEIGHTS["coef"], features(profile, c, now), strict=True)
        )
        scored.append((1 / (1 + math.exp(-z)), c["rule_score"], c["id"]))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))  # при равенстве — как правила
    return {
        "model_version": _WEIGHTS["model_version"],
        # reasons пустые: бэкенд покажет «Почему вы это видите» по правилам.
        "ranking": [{"id": cid, "score": round(p, 4), "reasons": []} for p, _, cid in scored],
    }


def rank_products(payload: dict) -> dict:
    """Кандидатов 1–3, обучать не на чем — сохраняем порядок бэкенда."""
    ids = [c["product"]["id"] for c in payload["candidates"]]
    n = len(ids)
    return {
        "model_version": "product-stub-0.1.0",
        "ranking": [
            {"product_id": pid, "score": (n - i) / n, "reasons": []} for i, pid in enumerate(ids)
        ],
    }
```

`reasons` оставляем пустыми — бэкенд покажет «Почему вы это видите» по правилам. Если останется время, можно писать свою причину по признаку с наибольшим вкладом (`вес × значение`), например `step_x_action` → `{"code": "status", "text": "Ваша заявка ждёт вашего действия"}`. Коды — только `okved | segment | product | status | general`.

Пример: Пекарня, заявка одобрена. Правила ставили первой отраслевую заметку, модель — подсказку к текущему шагу:

```
score  rule_score  новость
0.75   3.93        Что проверить перед подписанием договора
0.58   7.83        Пищевое производство: закупки сырья перед праздниками
0.52   3.93        Мука и сахар: чего ждать пекарням осенью
0.34   3.40        Печь в кредит: как посчитать окупаемость
```

## Шаг 6. README — `ml/README.md`

Жюри будет читать его. Коротко:

1. **Задача:** модель только меняет порядок новостей, которых уже отобрал бэкенд; кредитных решений не принимает; данные БКИ не использует.
2. **Данные:** синтетические, как получены (шаги 1–2), список гипотез из `interest`.
3. **Модель:** логистическая регрессия, список признаков, почему она (объяснимость, скорость, нет зависимостей на проде).
4. **Результат:** таблица NDCG@5 — модель / правила / случайно, на каком наборе.
5. **Ограничения:** модель выучила наши гипотезы, а не реальных клиентов. На реальных кликах повторяем шаги 3–6.
6. **Как воспроизвести:** команды шагов 1–4.
7. **Лицензии:** numpy, scikit-learn — BSD-3-Clause, pytest — MIT.

## Что сдать — чек-лист PR

- [ ] `ml/synth/{make_requests,simulate,features,train,ranking}.py`
- [ ] `ml/models/feed_ranker.json`
- [ ] `ml/tests/test_ranking.py` — `pytest` зелёный
- [ ] `ml/README.md` с таблицей NDCG@5
- [ ] `ml/data/` в `.gitignore`, данные не закоммичены
- [ ] код отформатирован: `cd backend && uv run ruff format ../ml && uv run ruff check ../ml`
- [ ] название PR и коммитов — что сделано, а не «simple fix»
- [ ] в PR отметить бэкендера: дальше он подключает `rank_feed` в `GET /feed` (таймаут 1 с, при сбое — правила, флаг `ML_RANKING_ENABLED`)

## Чего нельзя (условия кейса)

- никаких реальных данных, данных Альфа-Банка и скачанных датасетов о клиентах;
- никаких платных API и облачных моделей; LLM — только с открытыми весами (здесь LLM не нужна);
- модель не меняет набор новостей, только порядок; не трогает решения по кредиту;
- данные БКИ в ранжирование не идут.

## Если останется время

- поменять гипотезы и посмотреть, как меняются веса — хороший слайд для защиты;
- заменить регрессию на градиентный бустинг и сравнить NDCG — но тогда на проде нужна библиотека; регрессия проще;
- писать свои `reasons` (шаг 5);
- проверить, насколько результат зависит от seed: прогнать шаги 1–3 с 3–5 разными seed, в README — среднее и разброс.

"""Логистическая регрессия ленты: обучение и оценка на чистом Python (без numpy и sklearn).

Целевая функция — как у `sklearn.linear_model.LogisticRegression` (penalty="l2"):
    C · Σ logloss(y_i, σ(b + w·x_i)) + ½·‖w‖²,  свободный член b не штрафуется.
Решается методом Ньютона: 21 параметр, гессиан 21×21 — это быстро и точно.

Воспроизвести опубликованную модель (из корня репозитория):
    PYTHONPATH=.:backend python -m ml.synth.logreg --data ml/data/seed-42 \\
        --out ml/models/feed_logreg.json
Данные seed 42 создаются тем же генератором и симулятором, что в эксперименте ML-команды
(`make_requests.generate(seed=42)`, `simulate(seed=142, "mixed")`), если каталога ещё нет.
"""

import argparse
import csv
import hashlib
import json
import math
import random
from datetime import datetime
from pathlib import Path

from .features import FEATURE_VERSION, FEATURES, features

MODEL_VERSION = "feed-logreg-1.0.0"
C_GRID = (0.1, 1.0, 10.0)
REPO = Path(__file__).resolve().parents[2]


# ── Данные ────────────────────────────────────────────────────────────────────


def load(data: Path) -> dict[str, list[dict]]:
    """Запросы по частям train/validation/test: признаки, клики, вероятности, порядок правил."""
    clicks: dict[int, dict[str, tuple[int, float]]] = {}
    with (data / "clicks.csv").open() as f:
        for row in csv.DictReader(f):
            clicks.setdefault(int(row["request_id"]), {})[row["candidate_id"]] = (
                int(row["click"]),
                float(row["p_interest"]),
            )
    parts: dict[str, list[dict]] = {"train": [], "validation": [], "test": []}
    with (data / "requests.jsonl").open() as requests, (data / "metadata.jsonl").open() as meta:
        for line, meta_line in zip(requests, meta, strict=True):
            payload, info = json.loads(line), json.loads(meta_line)
            cands = payload["candidates"]
            ids = [c["id"] for c in cands]
            labels = clicks[info["request_id"]]
            parts[info["split"]].append(
                {
                    "client_id": info["client_id"],
                    "ids": ids,
                    "x": [features(payload["profile"], c, payload["now"]) for c in cands],
                    "click": [labels[i][0] for i in ids],
                    "interest": [labels[i][1] for i in ids],
                    # Порядок правил бэкенда (domain/feed_ranking.rank_news): вес, свежие, id.
                    "rules": sorted(
                        range(len(cands)),
                        key=lambda i: (
                            -cands[i]["rule_score"],
                            -datetime.fromisoformat(cands[i]["published_at"]).timestamp(),
                            ids[i],
                        ),
                    ),
                }
            )
    return parts


def ensure_data(data: Path, seed: int) -> None:
    if (data / "clicks.csv").exists():
        return
    from .make_requests import generate  # нужен код бэкенда (схемы, eligible_news)
    from .simulate import simulate

    generate(data, clients=4000, visits=3, seed=seed)
    simulate(data, seed=seed + 100, scenario="mixed")


# ── Обучение ──────────────────────────────────────────────────────────────────


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Гаусс с выбором главного элемента; матрица положительно определена (L2)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            if f:
                for k in range(col, n + 1):
                    m[r][k] -= f * m[col][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][k] * x[k] for k in range(r + 1, n))) / m[r][r]
    return x


def fit(rows: list[list[float]], y: list[int], c: float, tol: float = 1e-10) -> list[float]:
    """θ = [b, w₁…w_d], минимум C·Σ logloss + ½‖w‖². Возвращает θ."""
    d = len(rows[0]) + 1
    design = [[1.0, *r] for r in rows]
    theta = [0.0] * d
    for _ in range(50):
        grad = [0.0] * d
        hess = [[0.0] * d for _ in range(d)]
        for xi, yi in zip(design, y, strict=True):
            p = _sigmoid(sum(t * v for t, v in zip(theta, xi, strict=True)))
            g, h = c * (p - yi), c * p * (1 - p)
            for j in range(d):
                if xi[j]:
                    grad[j] += g * xi[j]
                    hj = h * xi[j]
                    row = hess[j]
                    for k in range(j, d):
                        if xi[k]:
                            row[k] += hj * xi[k]
        for j in range(1, d):  # штраф только на веса
            grad[j] += theta[j]
            hess[j][j] += 1.0
        for j in range(d):
            for k in range(j):
                hess[j][k] = hess[k][j]
        step = _solve(hess, grad)
        theta = [t - s for t, s in zip(theta, step, strict=True)]
        if max(abs(s) for s in step) < tol:
            break
    return theta


# ── Оценка ────────────────────────────────────────────────────────────────────


def ndcg(rel: list[float], order: list[int], k: int) -> float:
    """Как ml/synth/metrics.py ML-команды: линейный gain, запрос без положительных = 0."""

    def dcg(values: list[float]) -> float:
        return sum(float(v) / math.log2(i + 2) for i, v in enumerate(values[:k]))

    ideal = dcg(sorted(rel, reverse=True))
    return dcg([rel[i] for i in order]) / ideal if ideal > 0 else 0.0


def model_order(group: dict, theta: list[float]) -> list[int]:
    z = [theta[0] + sum(w * v for w, v in zip(theta[1:], x, strict=True)) for x in group["x"]]
    return sorted(range(len(z)), key=lambda i: (-z[i], group["ids"][i]))


def evaluate(
    groups: list[dict], theta: list[float] | None, seed: int = 0, digits: int | None = 4
) -> dict:
    """NDCG@3/@5 по кликам и oracle NDCG@5 для модели, правил, случайного порядка и оракула.

    digits=None — без округления (для выбора C: значения отличаются в 4-м знаке).
    """
    rnd = (lambda v: v) if digits is None else (lambda v: round(v, digits))
    rng = random.Random(seed)
    orders = {
        "logistic": (lambda g: model_order(g, theta)) if theta else None,
        "rules": lambda g: g["rules"],
        "random": lambda g: rng.sample(range(len(g["ids"])), len(g["ids"])),
        "oracle": lambda g: sorted(
            range(len(g["ids"])), key=lambda i: (-g["interest"][i], g["ids"][i])
        ),
    }
    result: dict = {
        "queries": len(groups),
        "zero_click_share": round(sum(not any(g["click"]) for g in groups) / len(groups), 4),
    }
    for name, make in orders.items():
        if make is None:
            continue
        c3 = c5 = o5 = 0.0
        for g in groups:
            o = make(g)
            c3 += ndcg(g["click"], o, 3)
            c5 += ndcg(g["click"], o, 5)
            o5 += ndcg(g["interest"], o, 5)
        n = len(groups)
        result[name] = {
            "ndcg@3": rnd(c3 / n),
            "ndcg@5": rnd(c5 / n),
            "oracle_ndcg@5": rnd(o5 / n),
        }
    return result


def _flatten(groups: list[dict]) -> tuple[list[list[float]], list[int]]:
    rows = [x for g in groups for x in g["x"]]
    labels = [y for g in groups for y in g["click"]]
    return rows, labels


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train(data: Path, seed: int = 42) -> dict:
    """Обучение на train, выбор C по validation NDCG@5, итог на test — как у ML-команды."""
    ensure_data(data, seed)
    parts = load(data)
    rows, labels = _flatten(parts["train"])
    trials = []
    for c in C_GRID:
        theta = fit(rows, labels, c)
        trials.append(
            {
                "C": c,
                "theta": theta,
                "validation": evaluate(parts["validation"], theta, seed, digits=None),
            }
        )
    best = max(trials, key=lambda t: t["validation"]["logistic"]["ndcg@5"])
    return {
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "features": FEATURES,
        "intercept": best["theta"][0],
        "coef": best["theta"][1:],
        "C": best["C"],
        "training": {
            "method": "Newton, L2 (C·Σlogloss + ½‖w‖², intercept unpenalized), pure Python",
            "data": "synthetic: ml/synth/make_requests.py seed 42 (4000 clients × 3 visits), "
            "clicks ml/synth/simulate.py seed 142, scenario mixed",
            "data_sha256": {
                name: _sha256(data / name)
                for name in ("requests.jsonl", "metadata.jsonl", "clicks.csv")
            },
            "train_rows": len(rows),
            "c_grid": [
                {"C": t["C"], "validation_ndcg@5": round(t["validation"]["logistic"]["ndcg@5"], 6)}
                for t in trials
            ],
        },
        "test_seed_42": evaluate(parts["test"], best["theta"], seed),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=REPO / "ml/data/seed-42")
    parser.add_argument("--out", type=Path, default=REPO / "ml/models/feed_logreg.json")
    args = parser.parse_args()
    model = train(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: model[k] for k in ("model_version", "C", "test_seed_42")}, indent=2))


if __name__ == "__main__":
    main()

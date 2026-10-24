"""Query-wise metrics. Empty-positive queries count as zero, also in XGBoost ndcg@5-."""

import math

import numpy as np


def ndcg(relevance, order, k: int) -> float:
    """Linear gains: binary clicks for primary metrics, probabilities for oracle diagnostics."""

    def dcg(values):
        return sum(float(v) / math.log2(i + 2) for i, v in enumerate(values[:k]))

    ideal = dcg(sorted(relevance, reverse=True))
    return dcg([relevance[i] for i in order]) / ideal if ideal > 0 else 0.0


def evaluate(groups: list[dict], scores: np.ndarray) -> tuple[dict, list[float]]:
    click3, click5, oracle5 = [], [], []
    empty = 0
    for group in groups:
        start, end = group["start"], group["end"]
        order = sorted(
            range(end - start), key=lambda i: (-float(scores[start + i]), group["ids"][i])
        )
        click3.append(ndcg(group["clicks"], order, 3))
        click5.append(ndcg(group["clicks"], order, 5))
        oracle5.append(ndcg(group["interest"], order, 5))
        empty += not any(group["clicks"])
    return {
        "ndcg@3": float(np.mean(click3)),
        "ndcg@5": float(np.mean(click5)),
        "oracle_ndcg@5": float(np.mean(oracle5)),
        "queries": len(groups),
        "zero_click_queries": empty,
        "ndcg@5_positive": float(sum(click5) / (len(groups) - empty))
        if len(groups) > empty
        else None,
        "ideal_observed_click_order_ndcg@5": (len(groups) - empty) / len(groups),
    }, click5


def paired_interval(a: list[float], b: list[float], groups: list[dict], seed: int) -> list[float]:
    """Cluster bootstrap: all requests of one held-out client move together."""
    by_client = {}
    for av, bv, group in zip(a, b, groups, strict=True):
        by_client.setdefault(group["client_id"], []).append(av - bv)
    totals = np.array([sum(v) for v in by_client.values()])
    counts = np.array([len(v) for v in by_client.values()])
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(1000):
        sample = rng.integers(0, len(totals), size=len(totals))
        estimates.append(totals[sample].sum() / counts[sample].sum())
    return [float(v) for v in np.quantile(estimates, [0.025, 0.975])]

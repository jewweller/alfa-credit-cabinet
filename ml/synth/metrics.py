"""Explicit exponential-gain NDCG for observed grades and linear gain for the oracle."""

import numpy as np


def ndcg(gains, scores, k):
    gains, scores = np.asarray(gains, dtype=float), np.asarray(scores, dtype=float)
    limit = min(k, len(gains))
    discounts = 1 / np.log2(np.arange(limit) + 2)
    ideal = float(np.sum(np.sort(gains)[::-1][:limit] * discounts))
    if ideal <= 0:
        return 0.0
    order = np.argsort(-scores, kind="stable")[:limit]
    return float(np.sum(gains[order] * discounts) / ideal)


def average_precision(labels, scores, k=3):
    relevant = np.asarray(labels) > 0
    order = np.argsort(-np.asarray(scores), kind="stable")[:k]
    selected = relevant[order]
    denominator = min(k, int(relevant.sum()))
    return (
        float(
            np.sum(np.cumsum(selected) / np.arange(1, len(selected) + 1) * selected) / denominator
        )
        if denominator
        else 0.0
    )


def grouped_metrics(frame, scores, *, oracle=False):
    metrics = {"ndcg@3": [], "ndcg@5": []}
    if not oracle:
        metrics["map@3"] = []
    indices = frame.reset_index(drop=True).groupby("qid", sort=False).indices
    zero_gain_queries = 0
    for index in indices.values():
        group = frame.iloc[index]
        gains = (
            group["ideal_relevance"].to_numpy(float)
            if oracle
            else np.exp2(group["label"].to_numpy(float)) - 1
        )
        if gains.sum() <= 0:
            zero_gain_queries += 1
            if oracle:
                # Nothing is approvable: there is no ideal ordering to recover.
                continue
        for k in (3, 5):
            metrics[f"ndcg@{k}"].append(ndcg(gains, np.asarray(scores)[index], k))
        if not oracle:
            metrics["map@3"].append(average_precision(group["label"], np.asarray(scores)[index]))
    return {
        "queries": len(indices),
        "evaluated_queries": len(metrics["ndcg@3"]),
        "zero_gain_queries": zero_gain_queries,
        **{key: float(np.mean(value)) if value else None for key, value in metrics.items()},
    }

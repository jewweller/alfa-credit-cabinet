import math

import numpy as np
import pytest
from ml.synth.metrics import evaluate, ndcg
from ml.synth.train import rules_scores


def test_ndcg_known_values_and_empty_queries():
    assert ndcg([1, 0], [0, 1], 2) == 1
    assert ndcg([1, 0], [1, 0], 2) == pytest.approx(1 / math.log2(3))
    assert ndcg([0, 0], [0, 1], 5) == 0
    assert ndcg([0.8, 0.2], [0, 1], 5) == 1


def test_metric_is_query_wise():
    groups = [
        {"start": 0, "end": 2, "ids": ["a", "b"], "clicks": [1, 0], "interest": [0.9, 0.1]},
        {"start": 2, "end": 4, "ids": ["a", "b"], "clicks": [0, 1], "interest": [0.1, 0.9]},
    ]
    metrics, _ = evaluate(groups, np.array([2, 1, 100, 101]))
    assert metrics["ndcg@5"] == 1


def test_rule_ties_use_publication_before_id():
    part = {
        "y": [0, 1],
        "rules": np.array([4, 4]),
        "groups": [
            {
                "start": 0,
                "end": 2,
                "ids": ["a", "z"],
                "published": ["2026-10-01T00:00:00Z", "2026-10-20T00:00:00Z"],
            }
        ],
    }
    scores = rules_scores(part)
    assert scores[1] > scores[0]


def test_positive_query_metric_does_not_change_primary_definition():
    groups = [
        {"start": 0, "end": 2, "ids": ["a", "b"], "clicks": [1, 0], "interest": [0.9, 0.1]},
        {"start": 2, "end": 4, "ids": ["a", "b"], "clicks": [0, 0], "interest": [0.1, 0.9]},
    ]
    metrics, _ = evaluate(groups, np.array([2, 1, 100, 101]))
    assert metrics["ndcg@5"] == 0.5
    assert metrics["ndcg@5_positive"] == 1
    assert metrics["ideal_observed_click_order_ndcg@5"] == 0.5


def test_positive_query_metric_undefined_when_all_queries_have_zero_clicks():
    groups = [{"start": 0, "end": 2, "ids": ["a", "b"], "clicks": [0, 0], "interest": [0.3, 0.2]}]
    metrics, _ = evaluate(groups, np.array([2, 1]))
    assert metrics["ndcg@5"] == 0
    assert metrics["ndcg@5_positive"] is None

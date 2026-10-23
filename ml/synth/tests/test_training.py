import json

import numpy as np
import pandas as pd
import pytest
from ml.synth.features import FEATURES
from ml.synth.metrics import average_precision, ndcg
from ml.synth.train import qids, train_run


def test_metrics_use_exponential_gains_for_observed_and_linear_oracle():
    gains = np.exp2([4, 1, 0]) - 1
    assert ndcg(gains, [3, 2, 1], 3) == 1
    assert ndcg(gains, [1, 2, 3], 3) < 1
    assert ndcg([0, 0], [1, 2], 3) == 0
    assert ndcg([0.9, 0.5, 0.1], [3, 2, 1], 3) == 1
    assert average_precision([0, 4, 1], [3, 2, 1]) == pytest.approx((0.5 + 2 / 3) / 2)


def test_qid_checks_order_and_encodes_groups():
    np.testing.assert_array_equal(qids(pd.DataFrame({"qid": ["a", "a", "b"]})), [0, 0, 1])
    with pytest.raises(ValueError, match="sorted"):
        qids(pd.DataFrame({"qid": ["b", "a", "b"]}))


@pytest.mark.parametrize("unbiased", [False, True])
def test_training_saved_model_report_and_ablations(run, tmp_path, unbiased):
    out = tmp_path / "model"
    report = train_run(run, out, estimators=8, unbiased=unbiased, ablations=not unbiased)
    assert (out / "ranker-0.1.0.json").is_file()
    assert json.loads((out / "features.json").read_text())["features"] == list(FEATURES)
    assert set(report["feature_importance"]) == set(FEATURES)
    assert report["deployment_ready"] is False
    if not unbiased:
        assert {"candidate_only", "shuffled_labels"} <= set(report["observed_all_shown"])
    assert report["oracle_all_candidates"]["ideal"]["ndcg@3"] == pytest.approx(1)
    assert 0 <= report["observed_positive_queries"]["model"]["ndcg@3"] <= 1

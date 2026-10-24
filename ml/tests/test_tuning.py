import numpy as np
import pytest
from ml.synth.dataset import load_dataset
from ml.synth.tune import join_audit, search_configs


def test_search_is_fixed_and_includes_initial_configuration():
    configs = search_configs(33)
    assert configs == search_configs(33)
    assert len(configs) == 33
    assert configs[0]["max_depth"] == 3
    assert configs[0]["min_child_weight"] == 20
    assert configs[0]["reg_lambda"] == 10
    assert {c["lambdarank_pair_method"] for c in configs} == {"mean", "topk"}
    assert {c["objective"] for c in configs} == {"rank:ndcg"}


def test_search_rejects_empty_trials():
    with pytest.raises(ValueError):
        search_configs(0)


def test_audit_join_keeps_every_query_aligned(generated):
    parts = load_dataset(generated)
    combined = join_audit(parts)
    assert len(combined["y"]) == sum(len(p["y"]) for p in parts.values())
    assert len(combined["groups"]) == 120
    assert len({g["client_id"] for g in combined["groups"]}) == 40
    cursor = 0
    for group in combined["groups"]:
        assert group["start"] == cursor
        np.testing.assert_array_equal(combined["y"][group["start"] : group["end"]], group["clicks"])
        cursor = group["end"]
    assert cursor == len(combined["y"])

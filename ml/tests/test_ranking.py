import copy
import json
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID

import numpy as np
import pytest
from app.schemas.ml import FeedRankRequest, FeedRankResponse, ProductRankResponse, is_permutation
from ml import rank_feed, rank_products, warmup
from ml.synth import ranking
from ml.synth.features import features

REPO = Path(__file__).resolve().parents[2]


def check_contract(payload):
    result = rank_feed(payload)
    parsed = FeedRankResponse.model_validate(result)
    assert is_permutation(
        [r.id for r in parsed.ranking], [UUID(c["id"]) for c in payload["candidates"]]
    )
    scores = [r.score for r in parsed.ranking]
    assert scores == sorted(scores, reverse=True)
    return result


def test_public_example_and_generated_requests_match_contract(payload, generated):
    check_contract(payload)
    for line in (generated / "requests.jsonl").read_text().splitlines():
        check_contract(json.loads(line))


def test_deterministic_without_mutation_and_input_order_independent(payload):
    original = copy.deepcopy(payload)
    first = rank_feed(payload)
    assert payload == original
    assert rank_feed(payload) == first
    payload["candidates"].reverse()
    assert rank_feed(payload) == first


@pytest.mark.parametrize("size", [1, 15])
def test_single_and_fifteen_candidates(payload, size):
    candidates = []
    for i in range(size):
        candidate = copy.deepcopy(payload["candidates"][i % len(payload["candidates"])])
        candidate["id"] = str(UUID(int=i + 1))
        candidates.append(candidate)
    payload["candidates"] = candidates
    FeedRankRequest.model_validate(payload)
    assert len(check_contract(payload)["ranking"]) == size


def test_duplicate_and_empty_candidates_rejected(payload):
    payload["candidates"].append(payload["candidates"][0])
    with pytest.raises(ValueError, match="unique"):
        rank_feed(payload)
    payload["candidates"] = []
    with pytest.raises(ValueError, match="At least"):
        rank_feed(payload)


def test_product_stub_preserves_order_and_contract():
    payload = json.loads((REPO / "docs/ml/product-rank.request.json").read_text())
    response = rank_products(payload)
    ProductRankResponse.model_validate(response)
    assert [r["product_id"] for r in response["ranking"]] == [
        c["product"]["id"] for c in payload["candidates"]
    ]


def test_product_stub_import_does_not_load_xgboost():
    code = "from ml import rank_products; import sys; assert 'xgboost' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_loaded_model_prediction_and_logistic_export(payload):
    model, _ = ranking._load_model()
    matrix = np.asarray(
        [features(payload["profile"], c, payload["now"]) for c in payload["candidates"]],
        dtype=np.float32,
    )
    expected = {
        c["id"]: ranking._sigmoid(float(s))
        for c, s in zip(payload["candidates"], model.predict(matrix), strict=True)
    }
    for row in rank_feed(payload)["ranking"]:
        assert row["score"] == expected[row["id"]]
    baseline = json.loads((ranking.MODEL_DIR / "logistic.json").read_text())
    logits = matrix @ np.asarray(baseline["coef"], dtype=baseline["dtype"]) + baseline["intercept"]
    assert np.isfinite(logits).all()


def test_mismatched_feature_manifest_is_rejected(payload, tmp_path, monkeypatch):
    metadata = json.loads((ranking.MODEL_DIR / "metadata.json").read_text())
    metadata["features"] = list(reversed(metadata["features"]))
    (tmp_path / "metadata.json").write_text(json.dumps(metadata))
    ranking._load_model.cache_clear()
    monkeypatch.setattr(ranking, "MODEL_DIR", tmp_path)
    try:
        with pytest.raises(RuntimeError, match="feature"):
            rank_feed(payload)
    finally:
        ranking._load_model.cache_clear()


def test_corrupted_model_is_rejected(payload, tmp_path, monkeypatch):
    metadata = (ranking.MODEL_DIR / "metadata.json").read_text()
    (tmp_path / "metadata.json").write_text(metadata)
    (tmp_path / "feed_ranker.ubj").write_bytes(b"corrupted")
    ranking._load_model.cache_clear()
    monkeypatch.setattr(ranking, "MODEL_DIR", tmp_path)
    try:
        with pytest.raises(RuntimeError, match="checksum"):
            rank_feed(payload)
    finally:
        ranking._load_model.cache_clear()


def test_warm_latency_with_fifteen_candidates(payload):
    payload["candidates"] = [
        {
            **copy.deepcopy(payload["candidates"][i % len(payload["candidates"])]),
            "id": str(UUID(int=i + 1)),
        }
        for i in range(15)
    ]
    rank_feed(payload)
    durations = []
    for _ in range(100):
        start = time.perf_counter()
        rank_feed(payload)
        durations.append(time.perf_counter() - start)
    assert np.quantile(durations, 0.95) < 1.0


def test_explicit_startup_warmup(payload):
    ranking._load_model.cache_clear()
    version = warmup()
    assert version == rank_feed(payload)["model_version"]
    assert ranking._load_model.cache_info().misses == 1

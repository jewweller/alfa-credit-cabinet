"""Public JSON-to-JSON API: XGBoost news ranking and a product-order stub."""

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

from .features import FEATURE_VERSION, FEATURES, features

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"


@lru_cache(maxsize=1)
def _load_model():
    # Lazy import keeps importing ml and calling rank_products possible without XGBoost.
    import xgboost as xgb

    metadata = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
    if metadata["features"] != FEATURES or metadata["feature_version"] != FEATURE_VERSION:
        raise RuntimeError("Model and feature definitions differ; retrain the model")
    path = MODEL_DIR / "feed_ranker.ubj"
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["model_sha256"]:
        raise RuntimeError("Model checksum does not match metadata")
    model = xgb.XGBRanker(n_jobs=1)
    model.load_model(path)
    model.set_params(n_jobs=1)
    if model.n_features_in_ != len(FEATURES):
        raise RuntimeError("Model feature count differs")
    return model, metadata


def warmup() -> str:
    """Load libraries/weights and run a prediction at service startup, before requests."""
    import numpy as np

    model, metadata = _load_model()
    model.predict(np.zeros((1, len(FEATURES)), dtype=np.float32))
    return metadata["model_version"]


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1 + exp)


def rank_feed(payload: dict) -> dict:
    """Return every candidate once. Scores are bounded ranking scores, not click probabilities."""
    import numpy as np

    candidates = payload["candidates"]
    ids = [str(c["id"]) for c in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("Candidate IDs must be unique")
    if not candidates:
        raise ValueError("At least one candidate is required")
    matrix = np.asarray(
        [features(payload["profile"], c, payload["now"]) for c in candidates], dtype=np.float32
    )
    if not np.isfinite(matrix).all():
        raise ValueError("Non-finite features")
    model, metadata = _load_model()
    scores = model.predict(matrix)
    if not np.isfinite(scores).all():
        raise RuntimeError("Model returned non-finite scores")
    # Stable tie-breaking independent of the candidate input order.
    ranked = sorted(zip(ids, scores, strict=True), key=lambda item: (-float(item[1]), item[0]))
    return {
        "model_version": metadata["model_version"],
        "ranking": [
            {"id": cid, "score": _sigmoid(float(score)), "reasons": []} for cid, score in ranked
        ],
    }


def rank_products(payload: dict) -> dict:
    """Keep backend product order; only the feed has an ML model."""
    ids = [str(c["product"]["id"]) for c in payload["candidates"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Candidate IDs must be unique")
    count = len(ids)
    return {
        "model_version": "product-stub-0.1.0",
        "ranking": [
            {"product_id": pid, "score": (count - i) / count, "reasons": []}
            for i, pid in enumerate(ids)
        ],
    }

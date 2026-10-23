"""Backend integration seam. RANKER_ENABLED should be passed as enabled by the API."""

import json
from pathlib import Path

from .features import FEATURES, baseline_b_key, build_feature_rows, model_frame


def rank_candidates(
    request, candidates, *, company, fns, bki, config, engine, enabled=False, model_directory=None
):
    """Rank an already hard-filtered candidate list, with deterministic baseline B fallback.

    This helper has no side effects and makes no credit decision. The current repository
    does not yet implement POST /products/recommend; wiring that endpoint is separate.
    """
    rows = build_feature_rows(
        request, candidates, company=company, fns=fns, bki=bki, config=config, engine=engine
    )
    if not rows:
        return []
    order = sorted(
        range(len(rows)), key=lambda i: (baseline_b_key(rows[i]), candidates[i]["candidate_id"])
    )
    if enabled and model_directory:
        from xgboost import XGBRanker
        from xgboost.core import XGBoostError

        try:
            directory = Path(model_directory)
            schema = json.loads((directory / "features.json").read_text())
            if schema["features"] != list(FEATURES):
                raise ValueError("incompatible feature schema")
            paths = sorted(directory.glob("ranker-*.json"))
            if len(paths) != 1:
                raise ValueError("expected one versioned ranker")
            model = XGBRanker()
            model.load_model(paths[0])
            scores = model.predict(model_frame(rows, schema["categories"]))
            order = sorted(order, key=lambda i: -float(scores[i]))
        except (OSError, ValueError, KeyError, XGBoostError):
            # Production adapter should emit an operational metric for this fallback.
            pass
    return [candidates[i] for i in order]

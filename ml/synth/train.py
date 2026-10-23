"""Offline ranker experiment with baselines, oracle metrics and leakage ablations."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRanker

from . import __version__
from .config import canonical_json
from .features import FEATURES, baseline_b_key, baseline_c_key, model_frame
from .metrics import grouped_metrics

CANDIDATE_ONLY = ["product_code", "cand_amount", "cand_term", "cand_rate", "cand_payment"]


def qids(frame):
    if not frame["qid"].is_monotonic_increasing:
        raise ValueError("qid must be sorted")
    return pd.factorize(frame["qid"], sort=True)[0].astype("uint32")


def fit_ranker(
    train,
    validation,
    vocabulary,
    params,
    *,
    seed,
    unbiased=False,
    columns=FEATURES,
    shuffle_labels=False,
):
    if train.empty or validation.empty:
        raise ValueError("empty train/validation split: increase --companies or history")
    x_train, x_val = (
        model_frame(train, vocabulary)[list(columns)],
        model_frame(validation, vocabulary)[list(columns)],
    )
    y_train, y_val = train["label"].to_numpy().copy(), validation["label"].to_numpy().copy()
    if shuffle_labels:
        rng = np.random.default_rng(seed)
        for frame, target in ((train, y_train), (validation, y_val)):
            for index in frame.groupby("qid", sort=False).indices.values():
                target[index] = rng.permutation(target[index])
    model = XGBRanker(
        objective="rank:ndcg",
        # XGBoost 3.0 requires binary labels for built-in MAP. Our funnel labels are
        # graded 0..4; binary MAP@3 is evaluated separately in metrics.py.
        eval_metric=["ndcg@5", "ndcg@3"],
        lambdarank_pair_method="topk",
        lambdarank_unbiased=unbiased,
        tree_method="hist",
        enable_categorical=True,
        random_state=seed % (2**32),
        **params,
    )
    model.fit(
        x_train,
        y_train,
        qid=qids(train),
        eval_set=[(x_val, y_val)],
        eval_qid=[qids(validation)],
        verbose=False,
    )
    return model


def baseline_scores(frame, key):
    scores = np.zeros(len(frame), dtype=float)
    records = frame.to_dict("records")
    for index in frame.groupby("qid", sort=False).indices.values():
        order = sorted(index, key=lambda i: (key(records[i]), records[i]["candidate_id"]))
        for rank, i in enumerate(order):
            scores[i] = -rank
    return scores


def evaluate(frame, predictions, rng, *, oracle=False):
    baselines = {
        "A_random": rng.random(len(frame)),
        "B_request_and_burden": baseline_scores(frame, baseline_b_key),
        "C_preliminary_rules": baseline_scores(frame, baseline_c_key),
        "ideal": frame["ideal_relevance"].to_numpy(),
        **predictions,
    }
    return {
        name: grouped_metrics(frame, scores, oracle=oracle) for name, scores in baselines.items()
    }


def train_run(
    data: str | Path, out: str | Path, *, estimators=None, unbiased=False, ablations=True
) -> dict:
    data, out = Path(data), Path(out)
    config = json.loads((data / "config.json").read_text())
    manifest = json.loads((data / "manifest.json").read_text())
    schema = json.loads((data / "features.json").read_text())
    if schema["features"] != list(FEATURES):
        raise ValueError("dataset feature version does not match this trainer")
    if out.exists():
        raise FileExistsError(f"training output exists: {out}")
    vocabulary, seed = schema["categories"], manifest["seed"]
    train = pd.read_parquet(data / "train.parquet")
    validation = pd.read_parquet(data / "validation.parquet")
    evaluation = pd.read_parquet(data / "evaluation.parquet", filters=[("split", "==", "test")])
    if evaluation.empty:
        raise ValueError("empty forward test window: increase --companies")
    truth = pd.read_parquet(
        data / "latent_truth.parquet", columns=["candidate_id", "ideal_relevance"]
    )
    evaluation = evaluation.merge(
        truth.dropna(subset="candidate_id"), on="candidate_id", validate="one_to_one"
    )
    evaluation = evaluation.sort_values(
        ["qid", "shown_position", "candidate_id"], kind="stable"
    ).reset_index(drop=True)
    params = dict(config["training"])
    if estimators is not None:
        if estimators < 1:
            raise ValueError("estimators must be positive")
        params["n_estimators"] = estimators
        params["early_stopping_rounds"] = min(
            params["early_stopping_rounds"], max(1, estimators // 4)
        )
    model = fit_ranker(train, validation, vocabulary, params, seed=seed, unbiased=unbiased)
    x_test = model_frame(evaluation, vocabulary)
    predictions = {"model": model.predict(x_test)}
    if ablations:
        candidate_model = fit_ranker(
            train, validation, vocabulary, params, seed=seed, columns=CANDIDATE_ONLY
        )
        shuffled_model = fit_ranker(
            train, validation, vocabulary, params, seed=seed, shuffle_labels=True
        )
        predictions["candidate_only"] = candidate_model.predict(x_test[CANDIDATE_ONLY])
        predictions["shuffled_labels"] = shuffled_model.predict(x_test)
    rng = np.random.default_rng(seed)
    shown_mask = evaluation["shown_position"].notna().to_numpy()
    positive_qids = set(evaluation.loc[evaluation["label"] > 0, "qid"])
    positive_mask = shown_mask & evaluation["qid"].isin(positive_qids).to_numpy()

    def subset_metrics(mask, *, oracle=False):
        return evaluate(
            evaluation[mask].reset_index(drop=True),
            {name: value[mask] for name, value in predictions.items()},
            rng,
            oracle=oracle,
        )

    report = {
        "seed": seed,
        "config_hash": manifest["config_hash"],
        "params": params,
        "position_debias": unbiased,
        "best_iteration": model.best_iteration,
        "cutoff_date": manifest["cutoff_date"],
        "counts": {
            "train_rows": len(train),
            "validation_rows": len(validation),
            "test_candidates": len(evaluation),
            "test_queries": evaluation.qid.nunique(),
        },
        "observed_all_shown": subset_metrics(shown_mask),
        "observed_positive_queries": subset_metrics(positive_mask),
        "oracle_all_candidates": subset_metrics(np.ones(len(evaluation), dtype=bool), oracle=True),
        "by_region": {},
        "by_segment": {},
        "feature_importance": dict(
            zip(FEATURES, model.feature_importances_.astype(float).tolist(), strict=True)
        ),
        "deployment_ready": False,
        "limitations": [
            "No agreed rollout threshold or funnel/grade corridors.",
            "Observed labels are selected by exposure; all-zero query NDCG is defined as zero.",
            "The ideal policy maximizes expected utility, not noisy observed labels.",
            "Candidate-only and shuffled-label experiments are diagnostics, not calibrated gates.",
            "Unbiased LambdaMART is opt-in: designed for clicks; "
            "graded funnel labels need validation.",
        ],
    }
    for field, destination in (("region_group", "by_region"), ("segment", "by_segment")):
        for value in sorted(evaluation[field].dropna().unique()):
            mask = evaluation[field].eq(value).to_numpy()
            report[destination][str(value)] = subset_metrics(mask, oracle=True)
    report["ndcg3_model_minus_B"] = (
        (
            report["observed_positive_queries"]["model"]["ndcg@3"]
            - report["observed_positive_queries"]["B_request_and_burden"]["ndcg@3"]
        )
        if positive_mask.any()
        else None
    )
    out.mkdir(parents=True)
    model_path = out / f"ranker-{__version__}.json"
    model.save_model(model_path)
    (out / "features.json").write_text(canonical_json(schema), encoding="utf-8")
    (out / "report.json").write_text(canonical_json(report), encoding="utf-8")
    # A usable artifact must round-trip, including categorical feature vocabulary/order.
    restored = XGBRanker()
    restored.load_model(model_path)
    np.testing.assert_array_equal(predictions["model"], restored.predict(x_test))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Train and evaluate an offline synthetic XGBRanker"
    )
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--estimators", type=int)
    parser.add_argument("--unbiased", action="store_true", help="experimental position debiasing")
    parser.add_argument("--no-ablations", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = train_run(
            args.data,
            args.out,
            estimators=args.estimators,
            unbiased=args.unbiased,
            ablations=not args.no_ablations,
        )
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(
        canonical_json(
            {
                "out": args.out,
                "ndcg3_model_minus_B": report["ndcg3_model_minus_B"],
                "deployment_ready": False,
            }
        ),
        end="",
    )


if __name__ == "__main__":
    main()

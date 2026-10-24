"""Train on clicks, select on validation, evaluate once on held-out clients."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import sklearn
import xgboost as xgb
from sklearn.linear_model import LogisticRegression

from .dataset import load_dataset
from .features import FEATURE_VERSION, FEATURES, as_datetime
from .metrics import evaluate, paired_interval

# Fixed search space; no test-set based tuning.
XGB_CONFIGS = [
    {"max_depth": 2, "min_child_weight": 10, "reg_lambda": 5},
    {"max_depth": 3, "min_child_weight": 20, "reg_lambda": 10},
    {"max_depth": 4, "min_child_weight": 30, "reg_lambda": 20},
]


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def rules_scores(part: dict) -> np.ndarray:
    """Reproduce backend tie-breaking: rule_score, newest publication, then ID."""
    scores = np.empty(len(part["y"]), dtype=float)
    for group in part["groups"]:
        start, end = group["start"], group["end"]
        order = sorted(
            range(end - start),
            key=lambda i: (
                -part["rules"][start + i],
                -as_datetime(group["published"][i]).timestamp(),
                group["ids"][i],
            ),
        )
        for position, index in enumerate(order):
            scores[start + index] = len(order) - position
    return scores


def train(data: Path, out: Path, seed: int = 42) -> dict:
    parts = load_dataset(data)
    fit, validation, test = (parts[s] for s in ("train", "validation", "test"))
    trials = {"logistic": [], "xgboost": []}
    logistic_models = []
    for c in (0.1, 1.0, 10.0):
        model = LogisticRegression(C=c, max_iter=2000, random_state=seed)
        model.fit(fit["X"], fit["y"])
        metric, _ = evaluate(validation["groups"], model.decision_function(validation["X"]))
        trials["logistic"].append({"C": c, "validation_ndcg@5": metric["ndcg@5"]})
        logistic_models.append(model)
    best_logistic = max(
        range(len(logistic_models)), key=lambda i: trials["logistic"][i]["validation_ndcg@5"]
    )
    logistic = logistic_models[best_logistic]
    rankers = []
    for config in XGB_CONFIGS:
        model = xgb.XGBRanker(
            objective="rank:ndcg",
            eval_metric="ndcg@5-",
            tree_method="hist",
            n_estimators=500,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=1.0,
            lambdarank_pair_method="mean",
            lambdarank_num_pair_per_sample=8,
            early_stopping_rounds=40,
            n_jobs=2,
            random_state=seed,
            **config,
        )
        model.fit(
            fit["X"],
            fit["y"],
            qid=fit["qid"],
            eval_set=[(validation["X"], validation["y"])],
            eval_qid=[validation["qid"]],
            verbose=False,
        )
        metric, _ = evaluate(validation["groups"], model.predict(validation["X"]))
        trials["xgboost"].append(
            {
                **config,
                "validation_ndcg@5": metric["ndcg@5"],
                "best_iteration": int(model.best_iteration),
            }
        )
        rankers.append(model)
    best_ranker = max(range(len(rankers)), key=lambda i: trials["xgboost"][i]["validation_ndcg@5"])
    ranker = rankers[best_ranker]

    # No selection below this point: test results cannot change models or parameters.
    predictions = {
        "rules": rules_scores(test),
        "logistic": logistic.decision_function(test["X"]),
        "xgboost": ranker.predict(test["X"]),
        "random": np.random.default_rng(seed + 2000).random(len(test["y"])),
    }
    metrics, query_values = {}, {}
    for name, scores in predictions.items():
        metrics[name], query_values[name] = evaluate(test["groups"], scores)
    intervals = {
        f"xgboost_minus_{baseline}": paired_interval(
            query_values["xgboost"], query_values[baseline], test["groups"], seed + 3000
        )
        for baseline in ("logistic", "rules")
    }
    out.mkdir(parents=True, exist_ok=True)
    ranker.save_model(out / "feed_ranker.ubj")
    # Baseline can also be evaluated without pickle or sklearn at inference time.
    (out / "logistic.json").write_text(
        json.dumps(
            {
                "features": FEATURES,
                "feature_version": FEATURE_VERSION,
                "dtype": str(logistic.coef_.dtype),
                "coef": logistic.coef_[0].tolist(),
                "intercept": float(logistic.intercept_[0]),
                "C": float(logistic.C),
            },
            indent=2,
        )
        + "\n"
    )
    metadata = {
        "model_version": f"feed-xgb-0.1.0-seed-{seed}",
        "feature_version": FEATURE_VERSION,
        "features": FEATURES,
        "model_sha256": digest(out / "feed_ranker.ubj"),
        "seed": seed,
        "selected_config": trials["xgboost"][best_ranker],
        "objective": "rank:ndcg",
        "selection_metric": "validation click NDCG@5",
        "score_transform": "sigmoid(raw ranking score); not a click probability",
        "versions": {
            "numpy": np.__version__,
            "scikit-learn": sklearn.__version__,
            "xgboost": xgb.__version__,
        },
        "data_sha256": {
            name: digest(data / name) for name in ("requests.jsonl", "metadata.jsonl", "clicks.csv")
        },
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    result = {
        "seed": seed,
        "generation": json.loads((data / "generation.json").read_text()),
        "simulation": json.loads((data / "simulation.json").read_text()),
        "splits": {
            name: {
                "clients": len({g["client_id"] for g in part["groups"]}),
                "requests": len(part["groups"]),
                "rows": len(part["y"]),
                "uniform_label_queries": sum(len(set(g["clicks"])) == 1 for g in part["groups"]),
            }
            for name, part in parts.items()
        },
        "validation_trials": trials,
        "test": metrics,
        "paired_client_bootstrap_95ci": intervals,
    }
    (out / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/seed-42"))
    parser.add_argument("--out", type=Path, default=Path("runs/seed-42"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = train(args.data, args.out, args.seed)
    print(json.dumps(result["test"], indent=2))


if __name__ == "__main__":
    main()

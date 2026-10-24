"""Validation-only search, cross-seed confirmation, then a fresh one-shot audit."""

import argparse
import copy
import json
import random
import shutil
from pathlib import Path

import numpy as np
import xgboost as xgb

from .dataset import load_dataset
from .make_requests import generate
from .metrics import evaluate, paired_interval
from .simulate import simulate
from .train import digest, rules_scores

ROOT = Path(__file__).resolve().parents[1]
TRAIN_SEEDS = [42, 43, 44]


def search_configs(trials: int, seed: int = 101) -> list[dict]:
    """First configuration exactly reproduces the current published model's training."""
    if trials < 2:
        raise ValueError("At least two trials are required")
    base = {
        "objective": "rank:ndcg",
        "eval_metric": "ndcg@5-",
        "tree_method": "hist",
        "n_estimators": 500,
        "learning_rate": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 1.0,
        "lambdarank_pair_method": "mean",
        "lambdarank_num_pair_per_sample": 8,
        "early_stopping_rounds": 40,
        "n_jobs": 2,
        "max_depth": 3,
        "min_child_weight": 20,
        "reg_lambda": 10,
    }
    result = [base]
    rng = random.Random(seed)
    seen = {json.dumps(base, sort_keys=True)}
    while len(result) < trials:
        method = rng.choice(["mean", "topk"])
        config = {
            **base,
            "n_estimators": 1000,
            "early_stopping_rounds": 70,
            "learning_rate": rng.choice([0.025, 0.05, 0.1, 0.15]),
            "max_depth": rng.choice([1, 2, 3, 4, 5, 6]),
            "min_child_weight": rng.choice([1, 5, 10, 20, 40, 80]),
            "reg_lambda": rng.choice([0.1, 1, 5, 10, 30]),
            "reg_alpha": rng.choice([0, 0.1, 1]),
            "subsample": rng.choice([0.7, 0.85, 1.0]),
            "colsample_bytree": rng.choice([0.8, 1.0]),
            "lambdarank_pair_method": method,
            "lambdarank_num_pair_per_sample": rng.choice([1, 4, 8])
            if method == "mean"
            else rng.choice([5, 8, 12]),
        }
        key = json.dumps(config, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(config)
    return result


def fit_trial(parts: dict, config: dict, seed: int, path: Path) -> dict:
    fit, validation = parts["train"], parts["validation"]
    model = xgb.XGBRanker(**config, random_state=seed)
    model.fit(
        fit["X"],
        fit["y"],
        qid=fit["qid"],
        eval_set=[(validation["X"], validation["y"])],
        eval_qid=[validation["qid"]],
        verbose=False,
    )
    metrics, _ = evaluate(validation["groups"], model.predict(validation["X"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(path)
    return {
        "seed": seed,
        "validation_ndcg@5": metrics["ndcg@5"],
        "best_iteration": int(model.best_iteration),
    }


def join_audit(parts: dict) -> dict:
    """All fresh clients are audit-only; generated split labels have no training role."""
    result = {"X": [], "y": [], "rules": [], "groups": []}
    offset = 0
    for part in parts.values():
        for field in ("X", "y", "rules"):
            result[field].append(part[field])
        for group in part["groups"]:
            result["groups"].append(
                {**group, "start": group["start"] + offset, "end": group["end"] + offset}
            )
        offset += len(part["y"])
    for field in ("X", "y", "rules"):
        result[field] = np.concatenate(result[field])
    return result


def audit_models(audit: dict, models: dict, baseline: dict, seed: int) -> dict:
    scores = {name: model.predict(audit["X"]) for name, model in models.items()}
    scores["logistic"] = audit["X"] @ np.asarray(baseline["coef"], dtype=baseline["dtype"])
    scores["logistic"] += baseline["intercept"]
    scores["rules"] = rules_scores(audit)
    # Diagnostic with privileged information, NEVER used in model selection.
    scores["oracle_interest_order"] = np.concatenate(
        [np.asarray(group["interest"]) for group in audit["groups"]]
    )
    results, query_values = {}, {}
    for name, prediction in scores.items():
        results[name], query_values[name] = evaluate(audit["groups"], prediction)
    intervals = {
        f"tuned_minus_{baseline_name}": paired_interval(
            query_values["tuned"], query_values[baseline_name], audit["groups"], seed
        )
        for baseline_name in ("initial", "logistic", "rules")
    }
    return {"metrics": results, "paired_client_bootstrap_95ci": intervals}


def write_report(report: dict, target: Path) -> None:
    target.write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Подбор гиперпараметров XGBoost",
        "",
        f"Проверено {report['trials']} конфигурации на validation seed 42; "
        f"{len(report['confirmation'])} финалистов проверены также на seed 43 и 44.",
        "Выбор — средний validation NDCG@5 трёх seed. Исходный test не используется.",
        "",
        "## Подтверждение по validation",
        "",
        "| Конфигурация | Seed 42 | Seed 43 | Seed 44 | Среднее |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in sorted(report["confirmation"], key=lambda r: -r["mean_validation_ndcg@5"]):
        values = " | ".join(f"{r['validation_ndcg@5']:.5f}" for r in item["seeds"])
        lines.append(f"| {item['trial']} | {values} | {item['mean_validation_ndcg@5']:.5f} |")
    lines += [
        "",
        f"Выбран trial {report['selected_trial']}. Параметры:",
        "",
        "```json",
        json.dumps(report["selected_config"], indent=2),
        "```",
        "",
        "## Новая независимая выборка",
        "",
        f"Seed {report['audit_seed']}: {report['audit_clients']} новых синтетических "
        "клиентов × 3 запроса. Все используются только для финальной оценки.",
        "",
        "| Модель | NDCG@5, все запросы | NDCG@5, есть клик | Oracle NDCG@5 |",
        "|---|---:|---:|---:|",
    ]
    for name, metric in report["audit"]["metrics"].items():
        positive = metric["ndcg@5_positive"]
        value = f"{positive:.5f}" if positive is not None else "n/a"
        lines.append(
            f"| {name} | {metric['ndcg@5']:.5f} | {value} | {metric['oracle_ndcg@5']:.5f} |"
        )
    metric = report["audit"]["metrics"]["tuned"]
    lines += [
        "",
        f"Без кликов: {metric['zero_click_queries']} из {metric['queries']}. "
        f"Максимум основной метрики при идеальной сортировке известных кликов: "
        f"{metric['ideal_observed_click_order_ndcg@5']:.5f}.",
        "",
        "`oracle_interest_order` знает скрытые вероятности симулятора: это диагностический "
        "ориентир, не обученная модель и не гарантированный максимум метрики на случайных кликах.",
        "",
        "95% CI разницы по основной метрике (bootstrap по клиентам):",
        "",
    ]
    for name, (lo, hi) in report["audit"]["paired_client_bootstrap_95ci"].items():
        lines.append(f"- {name}: [{lo:.5f}, {hi:.5f}]")
    lines += [
        "",
        "Выбор модели зафиксирован до генерации новой выборки в selection.json.",
        f"Обновление основной модели по validation: {report['promoted_by_validation']}.",
        "Симулятор, признаки и train-данные не изменялись.",
        "",
    ]
    target.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def run(
    trials: int = 33, finalists: int = 6, audit_clients: int = 4000, audit_seed: int = 20261024
) -> dict:
    if audit_seed in TRAIN_SEEDS or audit_clients < 10 or finalists < 1:
        raise ValueError("Audit must be independent; use >=10 clients and >=1 finalist")
    work = ROOT / "runs/tuning-v1"
    report_path = ROOT / "reports/tuning.json"
    # Never silently reuse an already inspected audit set for another round of tuning.
    if report_path.exists() or (work / "selection.json").exists():
        raise FileExistsError(
            "Tuning v1 is already frozen; define a new protocol/audit for a new run"
        )
    work.mkdir(parents=True, exist_ok=True)
    configs = search_configs(trials)
    protocol = {
        "configs": configs,
        "train_seeds": TRAIN_SEEDS,
        "audit_seed": audit_seed,
        "audit_clients": audit_clients,
        "finalists": finalists,
        "selection_metric": "mean validation click NDCG@5 across seeds 42/43/44",
        "unchanged_sources_sha256": {
            name: digest(ROOT / name)
            for name in ("synth/features.py", "synth/simulate.py", "synth/make_requests.py")
        },
    }
    (work / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    parts = load_dataset(ROOT / "data/seed-42")
    stage_one = []
    for index, config in enumerate(configs):
        result = fit_trial(parts, config, 42, work / f"trial-{index}/seed-42.ubj")
        stage_one.append({"trial": index, **result})
        print(
            f"trial {index + 1}/{trials}: validation={result['validation_ndcg@5']:.5f}, "
            f"trees={result['best_iteration'] + 1}",
            flush=True,
        )
        (work / "stage-one.json").write_text(json.dumps(stage_one, indent=2) + "\n")
    top = [r["trial"] for r in sorted(stage_one, key=lambda r: -r["validation_ndcg@5"])[:finalists]]
    shortlist = list(dict.fromkeys([0, *top]))  # Original configuration is always the control.
    confirmation = [{"trial": index, "seeds": [stage_one[index]]} for index in shortlist]
    del parts
    for seed in TRAIN_SEEDS[1:]:
        parts = load_dataset(ROOT / f"data/seed-{seed}")
        for item in confirmation:
            index = item["trial"]
            result = fit_trial(parts, configs[index], seed, work / f"trial-{index}/seed-{seed}.ubj")
            item["seeds"].append(result)
            print(
                f"confirm seed {seed}, trial {index}: validation={result['validation_ndcg@5']:.5f}",
                flush=True,
            )
        del parts
    for item in confirmation:
        item["mean_validation_ndcg@5"] = float(
            np.mean([r["validation_ndcg@5"] for r in item["seeds"]])
        )
    winner = max(confirmation, key=lambda r: r["mean_validation_ndcg@5"])
    selection = {
        "trial": winner["trial"],
        "config": configs[winner["trial"]],
        "confirmation": confirmation,
        "promote": winner["mean_validation_ndcg@5"] > confirmation[0]["mean_validation_ndcg@5"],
    }
    # Freeze the decision before ANY independent audit data are generated or scored.
    (work / "selection.json").write_text(json.dumps(selection, indent=2) + "\n")
    print(f"Selection frozen: trial {winner['trial']}; generating fresh audit", flush=True)
    initial_dir = ROOT / "models/initial"
    initial_dir.mkdir(exist_ok=True)
    for name in ("feed_ranker.ubj", "metadata.json", "logistic.json"):
        if not (initial_dir / name).exists():
            shutil.copyfile(ROOT / "models" / name, initial_dir / name)
    audit_data = ROOT / f"data/audit-{audit_seed}"
    generate(audit_data, clients=audit_clients, visits=3, seed=audit_seed)
    simulate(audit_data, seed=audit_seed + 100, scenario="mixed")
    audit = join_audit(load_dataset(audit_data))
    models = {}
    for name, path in {
        "initial": initial_dir / "feed_ranker.ubj",
        "tuned": work / f"trial-{winner['trial']}/seed-42.ubj",
    }.items():
        model = xgb.XGBRanker(n_jobs=2)
        model.load_model(path)
        model.set_params(n_jobs=2)
        models[name] = model
    baseline = json.loads((initial_dir / "logistic.json").read_text())
    audit_result = audit_models(audit, models, baseline, audit_seed + 1000)
    report = {
        "trials": trials,
        "confirmation": confirmation,
        "selected_trial": winner["trial"],
        "selected_config": selection["config"],
        "audit_seed": audit_seed,
        "audit_clients": audit_clients,
        "audit": audit_result,
        "promoted_by_validation": selection["promote"],
        "audit_data_sha256": {
            name: digest(audit_data / name)
            for name in ("requests.jsonl", "metadata.jsonl", "clicks.csv")
        },
    }
    # Publication is determined only by the already frozen validation decision.
    if selection["promote"]:
        metadata = copy.deepcopy(json.loads((initial_dir / "metadata.json").read_text()))
        models["tuned"].save_model(ROOT / "models/feed_ranker.ubj")
        metadata.update(
            model_version="feed-xgb-0.2.0-seed-42",
            model_sha256=digest(ROOT / "models/feed_ranker.ubj"),
            selected_config={
                **selection["config"],
                "best_iteration": int(models["tuned"].best_iteration),
            },
            selection_metric=protocol["selection_metric"],
            tuning_report="reports/tuning.json",
        )
        (ROOT / "models/metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    # Metadata for the search is small and reviewable; intermediate trial models stay ignored.
    (ROOT / "reports/tuning-protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    (ROOT / "reports/tuning-trials.json").write_text(json.dumps(stage_one, indent=2) + "\n")
    write_report(report, report_path)
    print(json.dumps(audit_result, indent=2), flush=True)
    return report


def reproduce() -> dict:
    """Refit only the already selected config; verify predictions without another search."""
    report = json.loads((ROOT / "reports/tuning.json").read_text())
    protocol = json.loads((ROOT / "reports/tuning-protocol.json").read_text())
    for name, expected in protocol["unchanged_sources_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Frozen data/feature source changed: {name}")
    data = ROOT / "data/seed-42"
    if not all(
        (data / name).exists() for name in ("requests.jsonl", "metadata.jsonl", "clicks.csv")
    ):
        initial = json.loads((ROOT / "reports/experiment.json").read_text())["runs"][0]
        generate(data, initial["generation"]["clients"], initial["generation"]["visits"], 42)
        simulate(data, initial["simulation"]["seed"], initial["simulation"]["scenario"])
    initial_metadata = json.loads((ROOT / "models/initial/metadata.json").read_text())
    for name, expected in initial_metadata["data_sha256"].items():
        if digest(data / name) != expected:
            raise ValueError(f"Training data changed: {name}")
    work = ROOT / "runs/tuning-reproduction"
    fitted = fit_trial(load_dataset(data), report["selected_config"], 42, work / "model.ubj")
    audit_data = ROOT / f"data/audit-{report['audit_seed']}"
    if not all((audit_data / name).exists() for name in report["audit_data_sha256"]):
        generate(audit_data, report["audit_clients"], 3, report["audit_seed"])
        simulate(audit_data, report["audit_seed"] + 100, "mixed")
    for name, expected in report["audit_data_sha256"].items():
        if digest(audit_data / name) != expected:
            raise ValueError(f"Frozen audit data changed: {name}")
    audit = join_audit(load_dataset(audit_data))
    reproduced = xgb.XGBRanker(n_jobs=2)
    reproduced.load_model(work / "model.ubj")
    published = xgb.XGBRanker(n_jobs=2)
    published.load_model(ROOT / "models/feed_ranker.ubj")
    prediction = reproduced.predict(audit["X"])
    np.testing.assert_array_equal(prediction, published.predict(audit["X"]))
    metric, _ = evaluate(audit["groups"], prediction)
    np.testing.assert_allclose(
        metric["ndcg@5"], report["audit"]["metrics"]["tuned"]["ndcg@5"], rtol=0, atol=1e-12
    )
    result = {"exact_prediction_parity": True, "audit_ndcg@5": metric["ndcg@5"], **fitted}
    (work / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=33)
    parser.add_argument("--finalists", type=int, default=6)
    parser.add_argument("--audit-clients", type=int, default=4000)
    parser.add_argument("--audit-seed", type=int, default=20261024)
    parser.add_argument("--reproduce", action="store_true")
    args = parser.parse_args()
    if args.reproduce:
        reproduce()
        return
    run(args.trials, args.finalists, args.audit_clients, args.audit_seed)


if __name__ == "__main__":
    main()

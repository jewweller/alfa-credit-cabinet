"""Reproducible full experiment; publish the first seed, never the best test seed."""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from .make_requests import generate
from .simulate import simulate
from .train import train

ROOT = Path(__file__).resolve().parents[1]


def run(seeds: list[int], clients: int, visits: int, sensitivity: bool = True) -> dict:
    results = []
    for seed in seeds:
        data, out = ROOT / f"data/seed-{seed}", ROOT / f"runs/seed-{seed}"
        print(f"seed={seed}: generating requests", flush=True)
        generate(data, clients, visits, seed)
        simulate(data, seed + 100, "mixed")
        result = train(data, out, seed)
        results.append(result)
        print(json.dumps({"seed": seed, "test": result["test"]}), flush=True)
    summary = {}
    for name in results[0]["test"]:
        summary[name] = {}
        for metric in ("ndcg@3", "ndcg@5", "oracle_ndcg@5"):
            values = [r["test"][name][metric] for r in results]
            summary[name][metric] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "values": values,
            }
    sensitivity_result = None
    if sensitivity:
        seed = seeds[0]
        data, out = ROOT / f"data/additive-{seed}", ROOT / f"runs/additive-{seed}"
        print("Additive scenario: sensitivity check", flush=True)
        generate(data, clients, visits, seed)
        simulate(data, seed + 100, "additive")
        sensitivity_result = train(data, out, seed)
        print(json.dumps({"additive": sensitivity_result["test"]}), flush=True)
    # Fixed in advance: publish seed 42 (or the first explicitly supplied seed).
    target, source = ROOT / "models", ROOT / f"runs/seed-{seeds[0]}"
    target.mkdir(exist_ok=True)
    for name in ("feed_ranker.ubj", "logistic.json", "metadata.json"):
        shutil.copyfile(source / name, target / name)
    report = {
        "published_seed": seeds[0],
        "summary": summary,
        "runs": results,
        "additive_sensitivity": sensitivity_result,
    }
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "experiment.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Результаты эксперимента",
        "",
        "Тест: новые синтетические клиенты. Среднее ± стандартное отклонение по seed.",
        "",
        "| Модель | NDCG@3, клики | NDCG@5, клики | Oracle NDCG@5 |",
        "|---|---:|---:|---:|",
    ]
    for name, metrics in summary.items():
        values = [
            f"{metrics[m]['mean']:.4f} ± {metrics[m]['std']:.4f}"
            for m in ("ndcg@3", "ndcg@5", "oracle_ndcg@5")
        ]
        lines.append("| " + name + " | " + " | ".join(values) + " |")
    lines += [
        "",
        "Oracle использует скрытую вероятность интереса и линейный gain; "
        "в обучении и выборе параметров она не участвует.",
        "",
        "## По каждому seed",
        "",
        "| Seed | LogReg NDCG@5 | XGB NDCG@5 | Δ XGB − LogReg, 95% CI |",
        "|---|---:|---:|---|",
    ]
    for result in results:
        lo, hi = result["paired_client_bootstrap_95ci"]["xgboost_minus_logistic"]
        lines.append(
            f"| {result['seed']} | {result['test']['logistic']['ndcg@5']:.4f} | "
            f"{result['test']['xgboost']['ndcg@5']:.4f} | [{lo:.4f}, {hi:.4f}] |"
        )
    if sensitivity_result:
        lines += [
            "",
            "## Проверка на аддитивном сценарии",
            "",
            "| Модель | NDCG@5, клики | Oracle NDCG@5 |",
            "|---|---:|---:|",
        ]
        for name, metrics in sensitivity_result["test"].items():
            lines.append(f"| {name} | {metrics['ndcg@5']:.4f} | {metrics['oracle_ndcg@5']:.4f} |")
    lines += [
        "",
        f"Публикуется модель первого заранее выбранного seed: {seeds[0]}.",
        "JSON рядом содержит размеры выборок, параметры и доверительные интервалы.",
        "",
    ]
    (reports / "metrics.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--clients", type=int, default=4000)
    parser.add_argument("--visits", type=int, default=3)
    parser.add_argument("--skip-sensitivity", action="store_true")
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("seeds must be unique")
    run(args.seeds, args.clients, args.visits, not args.skip_sensitivity)


if __name__ == "__main__":
    main()

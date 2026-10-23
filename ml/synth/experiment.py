"""Reproducible multi-seed experiment; report uncertainty instead of choosing a lucky seed."""

import argparse
from pathlib import Path

import numpy as np

from .config import DEFAULT_CONFIG, canonical_json, load_config
from .generate import generate
from .train import train_run


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate/train/evaluate over multiple seeds")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    parser.add_argument("--companies", type=int)
    parser.add_argument("--estimators", type=int)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if len(set(args.seeds)) < 3 or len(set(args.seeds)) != len(args.seeds):
        parser.error("provide at least three distinct seeds")
    root = Path(args.out)
    if root.exists():
        parser.error("--out must be a new directory")
    reports = []
    for seed in args.seeds:
        print(f"seed={seed}: generating", flush=True)
        run = generate(load_config(args.config), seed, root / "data", companies=args.companies)
        print(f"seed={seed}: training", flush=True)
        reports.append(train_run(run, root / "models" / f"seed-{seed}", estimators=args.estimators))
    summary = {"seeds": args.seeds, "runs": reports, "aggregate": {}, "deployment_ready": False}
    for scope in ("observed_all_shown", "observed_positive_queries", "oracle_all_candidates"):
        summary["aggregate"][scope] = {}
        for policy in reports[0][scope]:
            metrics = {}
            for metric in ("ndcg@3", "ndcg@5"):
                values = [
                    r[scope][policy][metric]
                    for r in reports
                    if r[scope][policy][metric] is not None
                ]
                metrics[metric] = {
                    "mean": float(np.mean(values)) if values else None,
                    "std": float(np.std(values, ddof=1)) if len(values) > 1 else None,
                    "values": values,
                }
            summary["aggregate"][scope][policy] = metrics
    (root / "summary.json").write_text(canonical_json(summary), encoding="utf-8")
    lines = [
        "# Multi-seed synthetic ranking experiment",
        "",
        f"Seeds: {args.seeds}",
        "",
        "| Evaluation | Policy | NDCG@3 mean ± sd | NDCG@5 mean ± sd |",
        "|---|---|---:|---:|",
    ]
    for scope, policies in summary["aggregate"].items():
        for policy, metrics in policies.items():
            values = [
                f"{metrics[m]['mean']:.4f} ± {metrics[m]['std']:.4f}"
                if metrics[m]["mean"] is not None and metrics[m]["std"] is not None
                else "insufficient data"
                for m in ("ndcg@3", "ndcg@5")
            ]
            lines.append(f"| {scope} | {policy} | {values[0]} | {values[1]} |")
    lines += [
        "",
        "Offline synthetic experiment; not approved for deployment.",
        "Observed metrics only use shown candidates. Oracle metrics use all eligible candidates.",
        "All-zero observed queries contribute zero in observed_all_shown.",
        "Full feature importance, subgroup diagnostics, limitations and parameters: summary.json.",
    ]
    (root / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(root / "REPORT.md")


if __name__ == "__main__":
    main()

"""One seeded stream, bounded buffers, atomic runs, reproducible byte-level manifests."""

import hashlib
import importlib.metadata
import shutil
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np

from . import __version__
from .behavior import simulate_funnel
from .candidates import generate_candidates
from .config import canonical_json, config_hash, validate_config
from .features import FEATURES, build_feature_rows, category_vocabulary
from .population import Population, weighted
from .quality import Diagnostics, data_card
from .rules import load_engine
from .splits import company_splits, cutoff_date, temporal_split
from .storage import Journals


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(
    config: dict, seed: int, out: str | Path, *, debug=False, companies=None, progress=None
) -> Path:
    config = deepcopy(config)
    if debug:
        config["simulation"]["companies"] = max(
            10, round(config["simulation"]["companies"] * config["simulation"]["debug_fraction"])
        )
    if companies is not None:
        config["simulation"]["companies"] = companies
    validate_config(config)
    if seed < 0:
        raise ValueError("seed must be nonnegative")
    engine = load_engine(config)
    tag = f"synth-v{__version__}-seed{seed}-{config_hash(config)}"
    parent = Path(out)
    parent.mkdir(parents=True, exist_ok=True)
    target, staging = parent / tag, parent / f".{tag}.tmp"
    if target.exists() or staging.exists():
        raise FileExistsError(f"run already exists: {target}; choose a different --out")
    staging.mkdir()
    try:
        rng = np.random.default_rng(seed)
        population = Population(config, rng)
        company_ids = [population.new_id() for _ in range(config["simulation"]["companies"])]
        assignment = company_splits(company_ids, config, seed)
        counts = [weighted(rng, config["simulation"]["requests_per_company"]) for _ in company_ids]
        # Assign a sorted UUID stream so every exported qid is globally sorted without
        # retaining the candidate/feature tables in memory. UUIDs carry no model signal.
        request_ids = iter(sorted(population.new_id() for _ in range(sum(counts))))
        diagnostics = Diagnostics(config)
        with Journals(staging, config) as journals:
            for company_number, (company_id, count) in enumerate(
                zip(company_ids, counts, strict=True), 1
            ):
                company, latent = population.company(company_id)
                journals.append("companies", company)
                diagnostics.company(company, latent)
                for created_at in population.dates(company, count):
                    request_id = next(request_ids)
                    fns, bki, revenue = population.profiles(company, latent, request_id, created_at)
                    request = population.request(company, request_id, created_at, revenue, bki)
                    split, exclusion = temporal_split(assignment[company_id], created_at, config)
                    candidates, empty = generate_candidates(
                        company, request, fns, bki, config, engine, population.new_id
                    )
                    features = build_feature_rows(
                        request,
                        candidates,
                        company=company,
                        fns=fns,
                        bki=bki,
                        config=config,
                        engine=engine,
                    )
                    # Full BKI is available to the simulated decision after application consent.
                    decisions = [engine.decide(company, request, c, fns, bki) for c in candidates]
                    scores = [engine.score(company, request, c, fns, bki) for c in candidates]
                    outcomes, truth, random_policy = simulate_funnel(
                        request, candidates, features, decisions, latent, config, rng
                    )
                    positive = any(o["label"] is not None and o["label"] > 0 for o in outcomes)
                    request.update(
                        company_split=assignment[company_id],
                        split=split,
                        exclusion_reason=exclusion,
                        empty_reason=empty,
                        candidate_count=len(candidates),
                        shown_count=sum(c["shown_position"] is not None for c in candidates),
                        random_policy=random_policy,
                        positive=positive,
                    )
                    journals.append("requests", request)
                    journals.append("fns_profiles", fns)
                    journals.append("bki_reports", bki)
                    if not truth:
                        journals.append(
                            "latent_truth",
                            {
                                "request_id": request_id,
                                "company_id": company_id,
                                "candidate_id": None,
                                **{
                                    key: latent[key]
                                    for key in (
                                        "latent_risk",
                                        "price_sensitivity",
                                        "urgency",
                                        "amount_flexibility",
                                        "term_preference",
                                    )
                                },
                            },
                        )
                    # Within each qid, shown order is preserved for XGBoost's implicit positions.
                    order = sorted(
                        range(len(candidates)),
                        key=lambda i: (
                            candidates[i]["shown_position"] or 100000,
                            candidates[i]["candidate_id"],
                        ),
                    )
                    for i in order:
                        candidate, outcome, row = candidates[i], outcomes[i], features[i]
                        shown = candidate["shown_position"] is not None
                        eligible = positive and shown and split != "excluded"
                        journals.append("candidates", candidate)
                        journals.append("outcomes", outcome)
                        journals.append("latent_truth", truth[i])
                        journals.append(
                            "evaluation",
                            {
                                "qid": request_id,
                                "candidate_id": candidate["candidate_id"],
                                "company_id": company_id,
                                "created_at": created_at,
                                "split": split,
                                "shown_position": candidate["shown_position"],
                                "random_policy": random_policy,
                                "training_eligible": eligible,
                                "label": outcome["label"],
                                **row,
                            },
                        )
                        if eligible:
                            journals.append(
                                split, {"qid": request_id, "label": outcome["label"], **row}
                            )
                    diagnostics.request(request, company, fns, bki, latent, scores, outcomes)
                if progress and (company_number % 100 == 0 or company_number == len(company_ids)):
                    progress(company_number, len(company_ids))
            row_counts = dict(journals.counts)
        (staging / "config.json").write_text(canonical_json(config), encoding="utf-8")
        (staging / "features.json").write_text(
            canonical_json({"features": list(FEATURES), "categories": category_vocabulary(config)}),
            encoding="utf-8",
        )
        root = Path(__file__).parent
        source_files = sorted(root.glob("*.py"))
        source_files += [root.parent / "uv.lock", root.parent.parent / "docs/plan.md"]
        manifest = {
            "generator_version": __version__,
            "seed": seed,
            "config_hash": config_hash(config),
            "rules_version": config["rules"]["version"],
            "rules_adapter": config["rules"]["adapter"],
            "python": sys.version.split()[0],
            "dependencies": {
                package: importlib.metadata.version(package)
                for package in (
                    "numpy",
                    "pandas",
                    "pyarrow",
                    "scipy",
                    "Faker",
                    "PyYAML",
                    "scikit-learn",
                    "xgboost",
                )
            },
            "source_sha256": {
                str(path.relative_to(root.parent.parent)): digest(path) for path in source_files
            },
            "cutoff_date": cutoff_date(config),
            "row_counts": row_counts,
            "synthetic": True,
            "deployment_ready": False,
        }
        report = diagnostics.report()
        (staging / "quality.json").write_text(canonical_json(report), encoding="utf-8")
        (staging / "DATA_CARD.md").write_text(data_card(report, manifest), encoding="utf-8")
        manifest["files_sha256"] = {path.name: digest(path) for path in sorted(staging.iterdir())}
        (staging / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
        staging.rename(target)
        return target
    except BaseException:
        shutil.rmtree(staging)
        raise

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from ml.synth.config import canonical_json, validate_config
from ml.synth.features import FEATURES, build_features
from ml.synth.generate import digest, generate
from ml.synth.inn import valid_inn
from ml.synth.rules import PlanRules
from ml.synth.storage import read_rows


def test_tables_funnel_and_contract_integrity(run, config):
    companies = {r["company_id"]: r for r in read_rows(run, "companies")}
    requests = {r["request_id"]: r for r in read_rows(run, "requests")}
    candidates = {r["candidate_id"]: r for r in read_rows(run, "candidates")}
    outcomes = read_rows(run, "outcomes")
    inns = [r["inn"] for r in companies.values()]
    assert len(inns) == len(set(inns))
    assert all(valid_inn(inn) for inn in inns)
    assert not set(inns) & set(config["company"]["reserved_inns"])
    assert all(r["name"].startswith("СИНТЕТИКА") for r in companies.values())
    assert all(not r["okved_extra"] for r in companies.values() if r["kind"] == "IE")
    for row in candidates.values():
        assert row["request_id"] in requests
        for name in ("amount", "rate", "monthly_payment"):
            assert re.fullmatch(r"\d+\.\d{2}", row[name])
    labels = set()
    for row in outcomes:
        candidate = candidates[row["candidate_id"]]
        request = requests[row["request_id"]]
        assert not row["issued"] or row["offer_accepted"]
        assert not row["offer_accepted"] or row["applied"]
        assert not row["applied"] or row["clicked"]
        assert not row["clicked"] or candidate["shown_position"] is not None
        if row["final_outcome"] == "rejected":
            assert row["label"] == 0
        if candidate["shown_position"] is None:
            assert row["label"] == (0 if request["random_policy"] else None)
        if row["label"] is not None:
            labels.add(row["label"])
    assert {0, 1, 2, 4} <= labels
    assert all(
        r["candidate_count"] <= config["candidates"]["max_candidates"] for r in requests.values()
    )
    assert sum(r["candidate_count"] == 0 for r in requests.values()) > 0


def test_point_in_time_and_consent(run):
    companies = {r["company_id"]: r for r in read_rows(run, "companies")}
    requests = {r["request_id"]: r for r in read_rows(run, "requests")}
    for row in read_rows(run, "fns_profiles"):
        request = requests[row["request_id"]]
        assert row["as_of"] == request["created_at"]
        assert companies[row["company_id"]]["registered_at"] < request["created_at"][:10]
        for year, value in row["revenue"].items():
            if value is not None:
                assert int(year) < int(request["created_at"][:4])
                assert int(year) >= int(companies[row["company_id"]]["registered_at"][:4])
    evaluation = pd.read_parquet(run / "evaluation.parquet")
    consent = {qid: r["bki_consent"] for qid, r in requests.items()}
    without = ~evaluation.qid.map(consent)
    assert evaluation.loc[without, [f for f in FEATURES if f.startswith("bki_")]].isna().all().all()


def test_group_time_split_and_training_schema(run):
    requests = pd.read_parquet(run / "requests.parquet")
    cutoff = json.loads((run / "manifest.json").read_text())["cutoff_date"]
    company_sets = {}
    for name in ("train", "validation", "test"):
        subset = requests[requests.split == name]
        company_sets[name] = set(subset.company_id)
        if name == "test":
            assert (subset.created_at.str[:10] >= cutoff).all()
        else:
            assert (subset.created_at.str[:10] < cutoff).all()
        frame = pd.read_parquet(run / f"{name}.parquet")
        assert list(frame.columns) == ["qid", "label", *FEATURES]
        assert frame.qid.is_monotonic_increasing
        assert (frame.groupby("qid", observed=True).label.max() > 0).all()
        assert set(frame.qid) <= set(subset.request_id)
    assert not company_sets["train"] & company_sets["validation"]
    assert not company_sets["train"] & company_sets["test"]
    assert not company_sets["validation"] & company_sets["test"]
    assert (requests.split == "excluded").any()


def test_shared_features_roundtrip_from_parquet(run, config):
    companies = {r["company_id"]: r for r in read_rows(run, "companies")}
    requests = {r["request_id"]: r for r in read_rows(run, "requests")}
    fns = {r["request_id"]: r for r in read_rows(run, "fns_profiles")}
    bki = {r["request_id"]: r for r in read_rows(run, "bki_reports")}
    candidates = {r["candidate_id"]: r for r in read_rows(run, "candidates")}
    rows = read_rows(run, "evaluation")
    for row in rows[:: max(1, len(rows) // 20)]:
        request = requests[row["qid"]]
        rebuilt = build_features(
            request,
            [candidates[row["candidate_id"]]],
            company=companies[row["company_id"]],
            fns=fns[row["qid"]],
            bki=bki[row["qid"]],
            config=config,
            engine=PlanRules(config),
        )
        for name in FEATURES:
            actual = rebuilt[name].iloc[0]
            if row[name] is None or (isinstance(row[name], float) and np.isnan(row[name])):
                assert pd.isna(actual)
            elif isinstance(row[name], float):
                assert actual == pytest.approx(row[name], rel=1e-6)
            else:
                assert actual == row[name]


def test_byte_reproducibility_across_processes_and_hash_seeds(tmp_path, config):
    config["simulation"]["companies"] = 20
    path = tmp_path / "config.yaml"
    path.write_text(canonical_json(config))  # JSON is a YAML subset.
    roots = [tmp_path / "a", tmp_path / "b"]
    for index, root in enumerate(roots):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "ml.synth",
                "--config",
                str(path),
                "--seed",
                "11",
                "--out",
                str(root),
            ],
            env=os.environ | {"PYTHONHASHSEED": str(index + 1)},
            cwd=Path(__file__).parents[3],
            check=True,
            capture_output=True,
        )
    left, right = (next(root.glob("synth-*")) for root in roots)
    assert {p.name: digest(p) for p in left.iterdir()} == {
        p.name: digest(p) for p in right.iterdir()
    }
    different = generate(config, 12, tmp_path / "c")
    assert digest(left / "companies.parquet") != digest(different / "companies.parquet")


def test_manifest_and_no_overwrite(run, config):
    manifest = json.loads((run / "manifest.json").read_text())
    for name, expected in manifest["files_sha256"].items():
        assert digest(run / name) == expected
    with pytest.raises(FileExistsError):
        generate(config, 42, run.parent, companies=200)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c["company"]["kinds"].update(weights=[0.8, 0.8]),
        lambda c: c["simulation"].update(companies=0),
        lambda c: c["request"].update(bki_consent_probability=1.1),
        lambda c: c["products"][0].update(min_term=100),
    ],
)
def test_invalid_config_fails_before_output(config, mutation, tmp_path):
    mutation(config)
    with pytest.raises(ValueError):
        validate_config(config)
    with pytest.raises(ValueError):
        generate(config, 42, tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()

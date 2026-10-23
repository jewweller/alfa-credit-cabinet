"""Validated, fully resolved configuration; no wall-clock defaults."""

import hashlib
import json
import math
from datetime import date
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).with_name("config.yaml")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def config_hash(config: dict) -> str:
    return hashlib.sha256(canonical_json(config).encode()).hexdigest()[:12]


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    with Path(path).open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ValueError("config.schema_version must be 1")
    # Reject typos and missing nested options, rather than quietly ignoring them.
    with DEFAULT_CONFIG.open(encoding="utf-8") as stream:
        template = yaml.safe_load(stream)

    def check_keys(value, expected, path="config"):
        if not isinstance(expected, dict):
            return
        if not isinstance(value, dict) or set(value) != set(expected):
            raise ValueError(f"{path}: expected keys {sorted(expected)}")
        for key in expected:
            check_keys(value[key], expected[key], f"{path}.{key}")

    check_keys(config, template)
    required = {
        "simulation",
        "company",
        "fns",
        "bki",
        "request",
        "candidates",
        "rules",
        "products",
        "behavior",
        "display",
        "split",
        "quality",
        "training",
        "schema_version",
    }
    if set(config) != required:
        raise ValueError(f"config sections must be {sorted(required)}")

    def walk(value, path="config"):
        if isinstance(value, dict):
            if "values" in value and "weights" in value:
                if len(value["values"]) != len(value["weights"]):
                    raise ValueError(f"{path}: values/weights lengths differ")
            for key, item in value.items():
                name = f"{path}.{key}"
                if key.endswith("weights") or key == "company_fractions":
                    if any(w < 0 for w in item) or not math.isclose(sum(item), 1, abs_tol=1e-9):
                        raise ValueError(f"{name}: nonnegative weights must sum to one")
                if key.endswith("probability") and not 0 <= item <= 1:
                    raise ValueError(f"{name}: probability must be in [0, 1]")
                if key.endswith("correlation") and not -1 < item < 1:
                    raise ValueError(f"{name}: correlation must be in (-1, 1)")
                if key.endswith("bounds") and (len(item) != 2 or item[0] >= item[1]):
                    raise ValueError(f"{name}: bounds must be increasing")
                if key.endswith("beta") and (len(item) != 2 or min(item) <= 0):
                    raise ValueError(f"{name}: beta parameters must be positive")
                if key.endswith("sigma") and item <= 0:
                    raise ValueError(f"{name}: sigma must be positive")
                walk(item, name)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                walk(item, f"{path}[{i}]")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{path}: must be finite")

    walk(config)
    sim = config["simulation"]
    if not isinstance(sim["companies"], int) or sim["companies"] < 10:
        raise ValueError("simulation.companies must be an integer >= 10")
    start, end = map(date.fromisoformat, (sim["start_date"], sim["end_date"]))
    if (end - start).days < 180 or not 1 <= config["split"]["test_months"] <= 5:
        raise ValueError("use at least 180 days of history and test_months in 1..5")
    if sim["parquet_batch_rows"] < 1 or not 0 < sim["debug_fraction"] <= 1:
        raise ValueError("invalid batch size or debug fraction")
    for collection in (config["company"]["industries"], config["company"]["regions"]):
        if not math.isclose(sum(item["weight"] for item in collection), 1, abs_tol=1e-9):
            raise ValueError("industry/region weights must sum to one")
        if len({item["code"] for item in collection}) != len(collection):
            raise ValueError("duplicate industry/region code")
    for industry in config["company"]["industries"]:
        if len(industry["purposes"]) != 3 or not math.isclose(sum(industry["purposes"]), 1):
            raise ValueError("industry purpose weights must contain three probabilities")
    codes = [p["code"] for p in config["products"]]
    if not codes or len(set(codes)) != len(codes):
        raise ValueError("product codes must be unique")
    for product in config["products"]:
        if not 0 < float(product["min_amount"]) <= float(product["max_amount"]):
            raise ValueError("invalid product amount bounds")
        if not 1 <= product["min_term"] <= product["max_term"]:
            raise ValueError("invalid product term bounds")
        if float(product["base_rate"]) < 0:
            raise ValueError("negative product rate")
    if not 5 <= config["candidates"]["max_candidates"] <= 100:
        raise ValueError("max_candidates must be in 5..100")
    if config["behavior"]["gumbel_scale"] <= 0:
        raise ValueError("gumbel_scale must be positive")
    if not 0 <= config["request"]["season_amplitude"] < 1:
        raise ValueError("season_amplitude must be in [0, 1)")
    if config["display"]["examination_exponent"] < 0:
        raise ValueError("examination_exponent must be nonnegative")
    if any(
        not isinstance(n, int) or not 1 <= n <= 5 for n in sim["requests_per_company"]["values"]
    ):
        raise ValueError("requests_per_company values must be integers in 1..5")
    if min(config["split"]["company_fractions"]) <= 0:
        raise ValueError("all split fractions must be positive")
    behavior = config["behavior"]
    if (
        not 0
        <= behavior["application_base"]
        <= behavior["application_base"] + behavior["application_urgency"]
        <= 1
    ):
        raise ValueError("application probability must remain in [0, 1]")
    rules = config["rules"]
    if not 0 < rules["dti_limit"] <= 1 or rules["term_step"] < 1:
        raise ValueError("invalid rule DTI limit or term step")
    if config["candidates"]["unknown_grade_for_pricing"] not in rules["rate_spreads"]:
        raise ValueError("unknown pricing grade")
    if sorted(config["rules"]["grade_thresholds"], reverse=True) != ["E", "D", "C", "B", "A"]:
        raise ValueError("grade thresholds must define A..E")

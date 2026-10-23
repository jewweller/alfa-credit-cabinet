from decimal import Decimal
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.scoring.config import CONFIG_PATH, load_config, parse_config


def _raw() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_repository_config_is_valid() -> None:
    config = load_config()

    assert config.config_version == "1.0.0"
    assert sum(f.max_points for f in config.scoring.factors.values()) == 100
    assert [g.grade for g in config.scoring.grades] == ["A", "B", "C", "D", "E"]


def test_numbers_are_decimal_not_float() -> None:
    raw = _raw()
    raw["calculation"]["debt_load"]["max_pct"] = 35.1

    config = parse_config(raw)

    assert config.calculation.debt_load.max_pct == Decimal("35.1")


def test_config_does_not_duplicate_product_catalog() -> None:
    # Продукты, лимиты и ставки — seed/products.json → БД; в конфиге их быть не должно.
    assert "products" not in _raw()
    assert "purposes" not in _raw()


def _mutated(path: list[str | int], value: Any) -> dict[str, Any]:
    raw = _raw()
    node = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return raw


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (["scoring", "factors", "F1", "bands", 1, "max_inclusive"], True, "попадает в 2"),
        (["scoring", "factors", "F3", "bands", 1, "min"], 26, "попадает в 0"),
        (["scoring", "factors", "F2", "bands", 0, "points"], 30, "сумма максимумов"),
        (["scoring", "grades", 1, "min_score"], 85, "убывать"),
        (["rules", "R4", "proof_document_kinds"], ["revenue_proof"], "proof_document_kinds"),
        (["reason_codes", "R6_GRADE_E", "client_reason"], None, "client_reason"),
        (["reason_codes", "R5_LARGE_AMOUNT", "rule"], "R11", "неизвестное правило"),
        (["calculation", "pricing", "grade_surcharge_pp"], {"A": 0, "B": 2}, "надбавки"),
    ],
    ids=[
        "overlap", "gap", "points-sum", "grades-order",
        "unknown-document-kind", "reject-without-client-reason", "unknown-rule", "no-surcharge",
    ],
)  # fmt: skip
def test_invalid_config_is_rejected(path: list[str | int], value: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_config(_mutated(path, value))


def test_missing_rule_is_rejected() -> None:
    raw = _raw()
    del raw["rules"]["R7"]

    with pytest.raises(ValidationError, match="R7"):
        parse_config(raw)


def test_r8_no_offer_outcome_follows_config() -> None:
    config = parse_config(_mutated(["rules", "R8", "on_no_offer"], "MANUAL_REVIEW"))

    assert config.outcome_of("R8_NO_OFFER") == "MANUAL_REVIEW"

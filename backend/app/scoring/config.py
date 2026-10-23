"""Загрузка и проверка scoring/config.yaml. Числа читаются как Decimal через str(), без float.

Ошибка в конфиге — исключение при загрузке: движок не должен работать на кривых порогах.
"""

from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.decisions import RejectReason
from app.schemas.documents import DocumentKind

CONFIG_PATH = Path(__file__).with_name("config.yaml")

FACTOR_IDS = ("F1", "F2", "F3", "F4", "F5", "F6")
RULE_IDS = tuple(f"R{n}" for n in range(1, 11))
GRADES = ("A", "B", "C", "D", "E")
Outcome = Literal["APPROVED", "COUNTER_OFFER", "REJECTED", "INFO_REQUESTED", "MANUAL_REVIEW"]
Grade = Literal["A", "B", "C", "D", "E"]

# Область значений фактора: целые или непрерывные, может ли быть отрицательным.
_UNIT_DOMAIN: dict[str, tuple[bool, bool]] = {
    "full_years": (True, False),
    "days": (True, False),
    "flags": (True, False),
    "percent": (False, True),
    "rub": (False, False),
}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Band(_Model):
    id: str
    min: Decimal | None = None
    max: Decimal | None = None
    min_inclusive: bool = True
    max_inclusive: bool = True
    points: int = Field(ge=0)

    def contains(self, value: Decimal) -> bool:
        if self.min is not None and (
            value < self.min or (value == self.min and not self.min_inclusive)
        ):
            return False
        return not (
            self.max is not None
            and (value > self.max or (value == self.max and not self.max_inclusive))
        )


class Factor(_Model):
    name: str
    source: str
    unit: Literal["full_years", "days", "flags", "percent", "rub"]
    bands: tuple[Band, ...]
    no_history_points: int | None = Field(default=None, ge=0)
    no_data_points: int | None = Field(default=None, ge=0)
    flags: tuple[str, ...] | None = None

    @property
    def max_points(self) -> int:
        extra = [p for p in (self.no_history_points, self.no_data_points) if p is not None]
        return max([b.points for b in self.bands] + extra)

    def band_for(self, value: Decimal) -> Band:
        matches = [b for b in self.bands if b.contains(value)]
        if len(matches) != 1:
            raise ValueError(f"{self.name}: значение {value} попало в {len(matches)} диапазонов")
        return matches[0]

    @model_validator(mode="after")
    def _bands_cover_domain_once(self) -> "Factor":
        integer, negative = _UNIT_DOMAIN[self.unit]
        step = Decimal(1) if integer else Decimal("0.001")
        bounds = {v for b in self.bands for v in (b.min, b.max) if v is not None}
        probes = {Decimal(0)} | {v + d for v in bounds for d in (-step, Decimal(0), step)}
        for probe in sorted(probes):
            if (probe < 0 and not negative) or (integer and probe != probe.to_integral_value()):
                continue
            count = sum(b.contains(probe) for b in self.bands)
            if count != 1:
                raise ValueError(f"{self.name}: значение {probe} попадает в {count} диапазонов")
        return self


class GradeThreshold(_Model):
    grade: Grade
    min_score: int = Field(ge=0)


class Scoring(_Model):
    max_total_points: int
    reference_date: date | None
    missing_source_points: int = Field(ge=0)
    grades: tuple[GradeThreshold, ...]
    factors: dict[str, Factor]

    @model_validator(mode="after")
    def _consistent(self) -> "Scoring":
        if tuple(self.factors) != FACTOR_IDS:
            raise ValueError(f"факторы должны быть ровно {FACTOR_IDS}")
        total = sum(f.max_points for f in self.factors.values())
        if total != self.max_total_points:
            raise ValueError(f"сумма максимумов F1–F6 = {total}, ожидается {self.max_total_points}")
        if tuple(g.grade for g in self.grades) != GRADES:
            raise ValueError(f"грейды должны идти в порядке {GRADES}")
        scores = [g.min_score for g in self.grades]
        if scores != sorted(scores, reverse=True) or len(set(scores)) != len(scores):
            raise ValueError("пороги грейдов должны строго убывать")
        if scores[-1] != 0:
            raise ValueError("последний грейд должен начинаться с 0")
        return self


class Rounding(_Model):
    mode: Literal["half_up", "down"]
    step_rub: Decimal = Field(gt=0)


class Calculation(_Model):
    annuity: dict[Literal["rate_conversion"], Literal["nominal_div_12"]]
    rounding: dict[Literal["payment", "amount", "interest"], Rounding]
    debt_load: "DebtLoad"
    pricing: "Pricing"


class DebtLoad(_Model):
    max_pct: Decimal = Field(gt=0)
    revenue_source: Literal["application", "min_application_fns"]
    include_bki_payments: bool


class Pricing(_Model):
    grade_surcharge_pp: dict[Grade, Decimal]


class RequestItem(_Model):
    kind: DocumentKind
    title: str
    required: bool
    # Какие виды документа закрывают пункт; пусто — только `kind`.
    accepts: tuple[DocumentKind, ...] = ()

    def accepted_kinds(self) -> set[str]:
        return {str(k) for k in (self.accepts or (self.kind,))}


class Rules(_Model):
    R1: dict[Literal["allowed_registry_statuses"], tuple[str, ...]]
    R2: dict[Literal["overdue_days_gt"], int]
    R3: dict[Literal["scope"], Literal["any_required_source"]]
    R4: "RuleR4"
    R5: dict[Literal["amount_rub_gt"], Decimal]
    R6: dict[Literal["grades"], tuple[Grade, ...]]
    R7: dict[Literal["grades"], tuple[Grade, ...]]
    R8: "RuleR8"
    R9: dict[Literal["grades"], tuple[Grade, ...]]
    R10: "RuleR10"


class RuleR4(_Model):
    mismatch_pct_gt: Decimal
    proof_document_kinds: tuple[DocumentKind, ...]
    request_items: tuple[RequestItem, ...]


class RuleR8(_Model):
    grades: tuple[Grade, ...]
    amount_share_pct: Decimal = Field(gt=0, le=100)
    on_no_offer: Literal["REJECTED", "MANUAL_REVIEW"]


class RuleR10(_Model):
    grades: tuple[Grade, ...]
    term_step_months: int = Field(ge=1)
    include_max_term_as_last_candidate: bool
    search_other_products: bool


class Integrations(_Model):
    timeout_sec: Decimal = Field(gt=0)
    retries: int = Field(ge=0)
    retry_delay_ms: int = Field(ge=0)
    retry_on: tuple[Literal["timeout", "connection_error", "http_5xx"], ...]
    no_retry_on: tuple[Literal["http_4xx"], ...]
    required_sources: dict[Literal["LLC", "IE"], tuple[str, ...]]
    registry_status_values: tuple[str, ...]


class Pipeline(_Model):
    max_step_attempts: int = Field(ge=1)
    step_retry_delay_sec: int = Field(ge=0)
    on_step_failure_reason_code: str


class ManualDecision(_Model):
    allowed_outcomes: tuple[Outcome, ...]
    enforce_product_limits: bool
    load_over_limit: Literal["block", "warn_require_comment", "allow"]
    comment_required: bool


class ReasonCode(_Model):
    rule: str
    outcome: Outcome | None = None
    outcome_ref: Literal["rules.R8.on_no_offer"] | None = None
    client_reason: RejectReason | None = None
    client_message: str
    client_next_step: str
    staff_message: str


class EngineConfig(_Model):
    config_version: str
    calculation: Calculation
    company: dict[Literal["kind_by_inn_length"], dict[int, Literal["LLC", "IE"]]]
    scoring: Scoring
    rules: Rules
    integrations: Integrations
    pipeline: Pipeline
    manual_decision: ManualDecision
    reason_codes: dict[str, ReasonCode]
    underwriter_rejection_reasons: dict[str, str]

    def outcome_of(self, code: str) -> Outcome:
        reason = self.reason_codes[code]
        if reason.outcome_ref == "rules.R8.on_no_offer":
            return self.rules.R8.on_no_offer
        assert reason.outcome is not None
        return reason.outcome

    @model_validator(mode="after")
    def _cross_checks(self) -> "EngineConfig":
        surcharge = self.calculation.pricing.grade_surcharge_pp
        for rule in (self.rules.R8, self.rules.R9, self.rules.R10):
            grades = rule.grades if isinstance(rule, RuleR8 | RuleR10) else rule["grades"]
            missing = [g for g in grades if g not in surcharge]
            if missing:
                raise ValueError(f"нет надбавки к ставке для грейдов {missing}")
        for code, reason in self.reason_codes.items():
            if (reason.outcome is None) == (reason.outcome_ref is None):
                raise ValueError(f"{code}: нужно ровно одно из outcome / outcome_ref")
            if reason.rule not in (*RULE_IDS, "system"):
                raise ValueError(f"{code}: неизвестное правило {reason.rule}")
            if self.outcome_of(code) == "REJECTED" and reason.client_reason is None:
                raise ValueError(f"{code}: для отказа нужен client_reason из контракта")
        if self.pipeline.on_step_failure_reason_code not in self.reason_codes:
            raise ValueError("pipeline.on_step_failure_reason_code: нет такого кода причины")
        return self


def _decimals(node: Any) -> Any:
    """Числа YAML → Decimal через str(), чтобы 0.1 не превратилось в 0.1000000000000000055."""
    if isinstance(node, bool) or node is None:
        return node
    if isinstance(node, int | float):
        return Decimal(str(node))
    if isinstance(node, dict):
        return {k: _decimals(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_decimals(v) for v in node]
    return node


def parse_config(raw: dict[str, Any]) -> EngineConfig:
    return EngineConfig.model_validate(_decimals(raw))


@lru_cache
def load_config(path: Path = CONFIG_PATH) -> EngineConfig:
    return parse_config(yaml.safe_load(path.read_text(encoding="utf-8")))

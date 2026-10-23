"""Plan reference adapter. Replace through the explicit adapter interface on integration.

Scoring uses the declared revenue and base rate, as in plan §7 examples.
Feature DTI uses FNS revenue. See DATA_CARD for the unresolved plan ambiguities.
"""

from dataclasses import dataclass
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Protocol

from .money import maximum_amount, money, monthly_payment


@dataclass(frozen=True)
class Score:
    total: int
    grade: str | None
    dti: float
    factors: tuple[int | None, ...]


@dataclass(frozen=True)
class Decision:
    outcome: str
    rule: str
    reason_code: str | None = None
    offer: dict | None = None


class RuleEngine(Protocol):
    def score(
        self, company: dict, request: dict, candidate: dict, fns: dict, bki: dict | None
    ) -> Score: ...

    def decide(
        self,
        company: dict,
        request: dict,
        candidate: dict,
        fns: dict,
        bki: dict | None,
        *,
        preliminary: bool = False,
    ) -> Decision: ...


def latest_revenue(fns: dict) -> tuple[float | None, float | None]:
    if not fns["available"] or not fns["revenue"]:
        return None, None
    years = sorted(year for year, value in fns["revenue"].items() if value is not None)
    if not years:
        return None, None
    last = float(fns["revenue"][years[-1]])
    previous = float(fns["revenue"][years[-2]]) if len(years) > 1 else None
    return last, last / previous - 1 if previous and previous > 0 else None


def visible_bki(request: dict, bki: dict | None) -> dict | None:
    return bki if request["bki_consent"] and bki and bki["available"] else None


def existing_payments(request: dict, bki: dict | None) -> float:
    if bki and bki["available"]:
        return sum(float(loan["monthly_payment"]) for loan in bki["loans"])
    return float(request["existing_payments_monthly"])


def age_years(company: dict, request: dict) -> float:
    asof = date.fromisoformat(request["created_at"][:10])
    registered = date.fromisoformat(company["registered_at"])

    def anniversary(year):
        try:
            return registered.replace(year=year)
        except ValueError:  # February 29 in a non-leap year.
            return registered.replace(year=year, day=28)

    years = asof.year - registered.year - int(asof < anniversary(asof.year))
    previous, following = (
        anniversary(registered.year + years),
        anniversary(registered.year + years + 1),
    )
    return years + (asof - previous).days / (following - previous).days


def hard_filter(company: dict, bki: dict | None) -> str | None:
    if company["status"] != "ACTIVE":
        return "R1"
    if bki and bki["available"] and (bki["bankruptcy"] or bki["current_overdue_days"] > 90):
        return "R2"
    return None


class PlanRules:
    def __init__(self, config: dict):
        self.config = config
        self.rules = config["rules"]
        self.products = {p["code"]: p for p in config["products"]}

    def score(self, company, request, candidate, fns, bki) -> Score:
        age = age_years(company, request)
        f1 = 0 if age < 1 else 8 if age < 2 else 15 if age <= 5 else 20
        if bki is None or not bki["available"]:
            f2 = None
        else:
            overdue = bki["max_overdue_days_24m"]
            f2 = (
                10
                if not bki["has_history"]
                else 25
                if overdue == 0
                else 15
                if overdue <= 30
                else 5
                if overdue <= 90
                else 0
            )
        product = self.products[candidate["product_code"]]
        payment = float(
            monthly_payment(candidate["amount"], product["base_rate"], candidate["term_months"])
        )
        dti = (existing_payments(request, bki) + payment) / (float(request["revenue_12m"]) / 12)
        f3 = 20 if dti <= 0.25 else 12 if dti <= 0.35 else 4 if dti <= 0.50 else 0
        _, growth = latest_revenue(fns)
        if fns["available"]:
            f4 = 8 if growth is None else 15 if growth >= 0 else 8 if growth >= -0.20 else 0
            debt = float(fns["tax_debt_rub"])
            f5 = 10 if debt == 0 else 4 if debt <= self.rules["tax_debt_threshold"] else 0
            flags = sum(fns["flags"].values())
            f6 = 10 if flags == 0 else 3 if flags == 1 else 0
        else:
            f4 = f5 = f6 = None
        factors = (f1, f2, f3, f4, f5, f6)
        total = sum(x for x in factors if x is not None)
        thresholds = self.rules["grade_thresholds"]
        grade = next(g for g in "ABCDE" if total >= thresholds[g]) if None not in factors else None
        return Score(total, grade, dti, factors)

    def _offer(self, product, amount, term, grade):
        rate = money(float(product["base_rate"]) + self.rules["rate_spreads"][grade])
        return {
            "product_code": product["code"],
            "amount": money(amount),
            "term_months": term,
            "rate": rate,
            "monthly_payment": monthly_payment(amount, rate, term),
        }

    def _affordable(self, request, bki, product, term, grade, maximum):
        rate = float(product["base_rate"]) + self.rules["rate_spreads"][grade]
        budget = float(request["revenue_12m"]) / 12 * self.rules["dti_limit"]
        budget -= existing_payments(request, bki)
        amount = maximum_amount(budget, rate, term, min(maximum, float(product["max_amount"])))
        if float(amount) < float(product["min_amount"]):
            return None
        return self._offer(product, amount, term, grade)

    def decide(self, company, request, candidate, fns, bki, *, preliminary=False) -> Decision:
        stop = hard_filter(company, bki)
        if stop:
            reason = "company_inactive" if stop == "R1" else "bankruptcy_or_overdue"
            return Decision("rejected", stop, reason)
        if not fns["available"] or (bki is not None and not bki["available"]):
            return Decision("manual_review", "R3")
        last, _ = latest_revenue(fns)
        if (
            last
            and abs(float(request["revenue_12m"]) - last) / last
            > self.rules["revenue_mismatch_limit"]
        ):
            outcome = (
                "manual_review" if request.get("documents_provided", False) else "info_requested"
            )
            return Decision(outcome, "R4")
        amount, term = float(candidate["amount"]), candidate["term_months"]
        if amount > self.rules["manual_amount"]:
            return Decision("manual_review", "R5")
        score = self.score(company, request, candidate, fns, bki)
        if score.grade is None:
            return Decision("manual_review", "BKI_REQUIRED" if preliminary else "R3")
        if score.grade == "E":
            return Decision("rejected", "R6", "low_score")
        if score.grade == "D":
            return Decision("manual_review", "R7")
        product = self.products[candidate["product_code"]]
        if score.grade == "C":
            offer = self._affordable(
                request, bki, product, term, "C", amount * self.rules["counter_amount_fraction"]
            )
            # The plan does not specify an impossible R8 offer. Apply product bounds,
            # then the existing no_suitable_terms outcome; never emit an invalid offer.
            return (
                Decision("counter_offer", "R8", offer=offer)
                if offer
                else Decision("rejected", "R8", "no_suitable_terms")
            )
        if score.dti <= self.rules["dti_limit"]:
            return Decision("approved", "R9", offer=self._offer(product, amount, term, score.grade))
        # R10: longer term, then smaller principal, then another purpose-compatible product.
        for months in range(
            term + self.rules["term_step"], product["max_term"] + 1, self.rules["term_step"]
        ):
            offer = self._offer(product, amount, months, score.grade)
            actual_dti = (existing_payments(request, bki) + float(offer["monthly_payment"])) / (
                float(request["revenue_12m"]) / 12
            )
            if actual_dti <= self.rules["dti_limit"]:
                return Decision("counter_offer", "R10", offer=offer)
        offer = self._affordable(request, bki, product, product["max_term"], score.grade, amount)
        if offer:
            return Decision("counter_offer", "R10", offer=offer)
        for other in self.products.values():
            if other["code"] == product["code"] or request["purpose"] not in other["purpose_tags"]:
                continue
            offer = self._affordable(request, bki, other, other["max_term"], score.grade, amount)
            if offer:
                return Decision("counter_offer", "R10", offer=offer)
        return Decision("rejected", "R10", "no_suitable_terms")


def load_engine(config: dict) -> RuleEngine:
    adapter = config["rules"]["adapter"]
    root = Path(__file__).resolve().parents[2]
    if adapter == "ml.synth.rules:PlanRules" and any(
        (root / "backend/app" / folder / "engine.py").exists() for folder in ("scoring", "decision")
    ):
        raise ValueError(
            "backend engines exist: configure rules.adapter to import them; "
            "refusing to silently use the plan reference engine"
        )
    module, name = adapter.split(":", 1)
    return getattr(import_module(module), name)(config)

"""Point-in-time company, external-source and request simulation."""

import math
from datetime import date, datetime, time, timedelta
from uuid import UUID

import numpy as np
from faker import Faker
from scipy.special import ndtr

from .inn import unique_inn
from .money import money


def weighted(rng, spec):
    index = int(rng.choice(len(spec["values"]), p=spec["weights"]))
    return spec["values"][index]


def correlated_uniform(rng, risk_z: float, correlation: float) -> float:
    return float(ndtr(correlation * risk_z + math.sqrt(1 - correlation**2) * rng.normal()))


def category_from_uniform(value: float, weights: list[float]) -> int:
    return min(int(np.searchsorted(np.cumsum(weights), value, side="right")), len(weights) - 1)


class Population:
    def __init__(self, config: dict, rng):
        self.config, self.rng = config, rng
        self.fake = Faker("ru_RU")
        self.fake.seed_instance(int(rng.integers(0, 2**32)))
        self.used_inns = set(config["company"]["reserved_inns"])
        self.start = date.fromisoformat(config["simulation"]["start_date"])
        self.end = date.fromisoformat(config["simulation"]["end_date"])

    def new_id(self) -> str:
        return str(UUID(bytes=self.rng.bytes(16), version=4))

    def company(self, company_id: str) -> tuple[dict, dict]:
        cfg, rng = self.config["company"], self.rng
        risk_z = float(rng.normal())
        risk = float(ndtr(risk_z))
        corr = cfg["risk_age_correlation"]
        age_z = corr * risk_z + math.sqrt(1 - corr**2) * rng.normal()
        age = float(
            np.clip(
                cfg["age_median_years"] * math.exp(cfg["age_log_sigma"] * age_z),
                cfg["age_min_years"],
                cfg["age_max_years"],
            )
        )
        registered = self.end - timedelta(days=round(age * 365.25))
        small = rng.random() < cfg["small_probability"]
        segment = "small" if small else "micro"
        corr = cfg["risk_revenue_correlation"]
        revenue_z = corr * risk_z + math.sqrt(1 - corr**2) * rng.normal()
        revenue = float(
            np.clip(
                cfg[f"{segment}_revenue_median"] * math.exp(cfg["revenue_log_sigma"] * revenue_z),
                *cfg[f"{segment}_revenue_bounds"],
            )
        )
        low, high = cfg[f"{segment}_employees"]
        rlow, rhigh = cfg[f"{segment}_revenue_bounds"]
        ratio = (math.log(revenue) - math.log(rlow)) / (math.log(rhigh) - math.log(rlow))
        employees = int(
            np.clip(
                round(low + ratio * (high - low) + rng.normal(0, cfg["employee_noise_sigma"])),
                low,
                high,
            )
        )
        industries = cfg["industries"]
        industry = industries[int(rng.choice(len(industries), p=[i["weight"] for i in industries]))]
        regions = cfg["regions"]
        region = regions[int(rng.choice(len(regions), p=[r["weight"] for r in regions]))]
        kind = weighted(rng, cfg["kinds"])
        # Adjacent industry families; extras remain absent for IE.
        adjacent = [
            i["code"]
            for i in industries
            if i["code"] != industry["code"]
            and abs(int(i["code"][:2]) - int(industry["code"][:2])) <= 5
        ]
        n_extra = (
            int(rng.integers(0, min(cfg["extra_okved_max"], len(adjacent)) + 1))
            if kind == "LLC"
            else 0
        )
        extras = (
            sorted(rng.choice(adjacent, size=n_extra, replace=False).tolist()) if n_extra else []
        )
        row = {
            "company_id": company_id,
            "inn": unique_inn(self.fake, kind, self.used_inns),
            "kind": kind,
            "status": weighted(rng, cfg["statuses"]),
            "registered_at": registered.isoformat(),
            "okved_main": industry["code"],
            "okved_extra": extras,
            "region": region["code"],
            "segment": segment,
            "employees": employees,
            "name": "СИНТЕТИКА — " + self.fake.company(),
            "director_fio": self.fake.name() if kind == "LLC" else None,
            "address": self.fake.address() if kind == "LLC" else None,
        }
        fc = self.config["fns"]
        growth = float(
            np.clip(
                rng.normal(fc["annual_growth_mean"], fc["annual_growth_sigma"]),
                *fc["annual_growth_bounds"],
            )
        )
        bc = self.config["behavior"]
        latent = {
            "latent_risk": risk,
            "risk_z": risk_z,
            "annual_revenue": revenue,
            "growth": growth,
            "price_sensitivity": float(rng.lognormal(*bc["price_sensitivity_lognormal"])),
            "urgency": float(rng.beta(*bc["urgency_beta"])),
            "amount_flexibility": float(rng.beta(*bc["amount_flexibility_beta"])),
            "term_preference": float(np.clip(rng.normal(1, bc["term_preference_sigma"]), 0.5, 1.5)),
        }
        return row, latent

    def dates(self, company: dict, count: int) -> list[str]:
        start = max(self.start, date.fromisoformat(company["registered_at"]) + timedelta(days=1))
        days = (self.end - start).days + 1
        if days < count:
            raise ValueError("not enough days after registration for distinct requests")
        available = [start + timedelta(days=i) for i in range(days)]
        industry = next(
            i for i in self.config["company"]["industries"] if i["code"] == company["okved_main"]
        )
        amp = self.config["request"]["season_amplitude"]
        weights = np.array(
            [
                1 + amp * math.cos(2 * math.pi * (d.month - industry["season_peak"]) / 12)
                for d in available
            ]
        )
        chosen = sorted(
            self.rng.choice(days, count, replace=False, p=weights / weights.sum()).tolist()
        )
        return [datetime.combine(available[i], time(12)).isoformat() + "+00:00" for i in chosen]

    def profiles(self, company: dict, latent: dict, request_id: str, created_at: str):
        rng, config = self.rng, self.config
        asof = date.fromisoformat(created_at[:10])
        registered = date.fromisoformat(company["registered_at"])
        age = (asof - registered).days / 365.25
        latest_year = asof.year - 1
        revenue = latent["annual_revenue"] / (1 + latent["growth"]) ** (
            self.end.year - 1 - latest_year
        )
        revenue = float(
            np.clip(revenue, *config["company"][f"{company['segment']}_revenue_bounds"])
        )
        annual = {}
        if latest_year >= registered.year:
            annual[str(latest_year)] = money(revenue)
        if age >= 1 and latest_year - 1 >= registered.year:
            annual[str(latest_year - 1)] = money(revenue / (1 + latent["growth"]))
        fc, bc = config["fns"], config["bki"]
        debt_bucket = category_from_uniform(
            correlated_uniform(rng, latent["risk_z"], fc["risk_correlation"]), fc["debt_weights"]
        )
        debt = (
            0
            if debt_bucket == 0
            else rng.uniform(*fc["small_debt_bounds"])
            if debt_bucket == 1
            else rng.uniform(*fc["large_debt_bounds"])
        )
        flags = {
            key: correlated_uniform(rng, latent["risk_z"], fc["risk_correlation"])
            > 1 - fc["flag_probability"]
            for key in ("mass_address", "unreliable_address", "unreliable_director")
        }
        fns = {
            "request_id": request_id,
            "company_id": company["company_id"],
            "as_of": created_at,
            "revenue": annual,
            "tax_debt_rub": money(debt),
            "msp_category": company["segment"],
            "employees": max(
                1,
                company["employees"]
                + int(round(rng.normal(0, config["company"]["employee_noise_sigma"]))),
            ),
            "flags": flags,
            "available": bool(rng.random() >= fc["unavailable_probability"]),
        }
        history = bool(
            rng.random()
            < (bc["young_history_probability"] if age < 1 else bc["history_probability"])
        )
        n_loans = weighted(rng, bc["loans_count"]) if history else 0
        uniform = correlated_uniform(rng, latent["risk_z"], bc["risk_correlation"])
        overdue_bucket = category_from_uniform(uniform, bc["overdue_weights"])
        current_bucket = category_from_uniform(uniform, bc["current_overdue_weights"])
        low, high = bc["overdue_ranges"][overdue_bucket]
        overdue = int(rng.integers(low, high + 1)) if history else 0
        low, high = bc["overdue_ranges"][current_bucket]
        current = int(rng.integers(low, high + 1)) if n_loans else 0
        overdue = max(current, overdue)
        total_payment = revenue / 12 * rng.beta(*bc["existing_dti_beta"]) if n_loans else 0
        shares = rng.dirichlet(np.ones(n_loans)) if n_loans else []
        loans = []
        for i, share in enumerate(shares):
            payment = money(total_payment * share)
            loans.append(
                {
                    "type": "business_loan",
                    "balance": money(float(payment) * rng.uniform(*bc["balance_months"])),
                    "monthly_payment": payment,
                    "max_overdue_days_24m": overdue if i == 0 else 0,
                    "current_overdue_days": current if i == 0 else 0,
                }
            )
        report = {
            "request_id": request_id,
            "company_id": company["company_id"],
            "as_of": created_at,
            "report_id": self.new_id(),
            "has_history": history,
            "bankruptcy": correlated_uniform(rng, latent["risk_z"], bc["risk_correlation"])
            > 1 - bc["bankruptcy_probability"],
            "loans": loans,
            "max_overdue_days_24m": overdue,
            "current_overdue_days": current,
            "inquiries_30d": int(
                rng.poisson(
                    bc["inquiry_lambda"]
                    * (1 + bc["inquiry_risk_multiplier"] * (latent["latent_risk"] - 0.5))
                )
            ),
            "available": bool(rng.random() >= bc["unavailable_probability"]),
        }
        return fns, report, revenue

    def request(self, company, request_id, created_at, revenue, bki):
        cfg, rng = self.config["request"], self.rng
        industry = next(
            i for i in self.config["company"]["industries"] if i["code"] == company["okved_main"]
        )
        purpose = cfg["purposes"][int(rng.choice(3, p=industry["purposes"]))]
        lo, hi = cfg["amount_share_bounds"]
        amount = revenue * (lo + (hi - lo) * rng.beta(*cfg["amount_beta"]))
        amount = max(
            cfg["amount_rounding"], round(amount / cfg["amount_rounding"]) * cfg["amount_rounding"]
        )
        mismatch_bucket = int(rng.choice(3, p=cfg["mismatch_weights"]))
        deviation = rng.uniform(*cfg["mismatch_ranges"][mismatch_bucket])
        declared = revenue * (1 + deviation * rng.choice([-1, 1]))
        payments = sum(float(loan["monthly_payment"]) for loan in bki["loans"])
        if rng.random() < cfg["understatement_probability"]:
            payments *= rng.uniform(*cfg["understated_payment_fraction"])
        return {
            "request_id": request_id,
            "company_id": company["company_id"],
            "created_at": created_at,
            "purpose": purpose,
            "amount_requested": money(amount),
            "term_requested": weighted(rng, cfg["terms"][purpose]),
            "revenue_12m": money(declared),
            "existing_payments_monthly": money(payments),
            "bki_consent": bool(rng.random() < cfg["bki_consent_probability"]),
        }

"""The only feature builder, shared by offline generation and future recommendation API.

Callers supply point-in-time snapshots. Consent and availability are enforced here,
even if a caller accidentally passes the complete BKI report.
"""

import math

import pandas as pd

from .rules import age_years, existing_payments, latest_revenue, visible_bki

CATEGORICAL = (
    "purpose",
    "kind",
    "segment",
    "okved_group",
    "region_group",
    "product_code",
    "pre_grade",
    "rule_hint",
)
FEATURES = (
    "purpose",
    "amount_requested",
    "log_amount_requested",
    "term_requested",
    "amount_to_revenue",
    "business_age_years",
    "kind",
    "segment",
    "okved_group",
    "region_group",
    "employees",
    "revenue_last",
    "revenue_growth",
    "revenue_mismatch",
    "tax_debt_bucket",
    "risk_flags_count",
    "bki_has_history",
    "bki_max_overdue_bucket",
    "bki_loans_count",
    "bki_inquiries_30d",
    "existing_payments_monthly",
    "product_code",
    "cand_amount",
    "cand_term",
    "cand_rate",
    "cand_payment",
    "amount_ratio",
    "term_delta",
    "purpose_match",
    "dti",
    "dti_bucket",
    "pre_score",
    "pre_grade",
    "rule_hint",
)


def bucket(value: float, thresholds: tuple[float, ...]) -> int:
    return sum(value > bound for bound in thresholds)


def category_vocabulary(config: dict) -> dict[str, list[str]]:
    return {
        "purpose": config["request"]["purposes"],
        "kind": config["company"]["kinds"]["values"],
        "segment": ["micro", "small"],
        "okved_group": sorted({i["code"][:2] for i in config["company"]["industries"]} | {"other"}),
        "region_group": sorted({r["group"] for r in config["company"]["regions"]} | {"other"}),
        "product_code": [p["code"] for p in config["products"]],
        "pre_grade": list("ABCDE") + ["UNKNOWN"],
        "rule_hint": [f"R{i}" for i in range(1, 11)] + ["BKI_REQUIRED"],
    }


def model_frame(rows: list[dict] | pd.DataFrame, vocabulary: dict) -> pd.DataFrame:
    frame = pd.DataFrame(rows).reindex(columns=FEATURES).copy()
    for name in FEATURES:
        if name in CATEGORICAL:
            frame[name] = pd.Categorical(frame[name], categories=vocabulary[name])
        else:
            frame[name] = pd.to_numeric(frame[name], errors="raise").astype("float32")
    return frame


def build_feature_rows(request, candidates, *, company, fns, bki, config, engine) -> list[dict]:
    bureau = visible_bki(request, bki)
    revenue, growth = latest_revenue(fns)
    amount = float(request["amount_requested"])
    declared = float(request["revenue_12m"])
    payments = existing_payments(request, bureau)
    products = {p["code"]: p for p in config["products"]}
    regions = {r["code"]: r["group"] for r in config["company"]["regions"]}
    known_okved = {i["code"][:2] for i in config["company"]["industries"]}
    base = {
        "purpose": request["purpose"],
        "amount_requested": amount,
        "log_amount_requested": math.log(amount),
        "term_requested": request["term_requested"],
        "amount_to_revenue": amount / declared,
        "business_age_years": age_years(company, request),
        "kind": company["kind"],
        "segment": company["segment"],
        "okved_group": company["okved_main"][:2]
        if company["okved_main"][:2] in known_okved
        else "other",
        "region_group": regions.get(company["region"], "other"),
        "employees": company["employees"],
        "revenue_last": revenue,
        "revenue_growth": growth,
        "revenue_mismatch": abs(declared - revenue) / revenue if revenue else None,
        "tax_debt_bucket": bucket(float(fns["tax_debt_rub"]), (0, 100000))
        if fns["available"]
        else None,
        "risk_flags_count": sum(fns["flags"].values()) if fns["available"] else None,
        "bki_has_history": int(bureau["has_history"]) if bureau else None,
        "bki_max_overdue_bucket": bucket(bureau["max_overdue_days_24m"], (0, 30, 90))
        if bureau
        else None,
        "bki_loans_count": len(bureau["loans"]) if bureau else None,
        "bki_inquiries_30d": bureau["inquiries_30d"] if bureau else None,
        "existing_payments_monthly": payments,
    }
    result = []
    for candidate in candidates:
        cand_amount = float(candidate["amount"])
        payment = float(candidate["monthly_payment"])
        score = engine.score(company, request, candidate, fns, bureau)
        # Unavailable bureau with consent is R3, absent consent is BKI_REQUIRED.
        hint_bki = bki if request["bki_consent"] else None
        decision = engine.decide(company, request, candidate, fns, hint_bki, preliminary=True)
        dti = (payments + payment) / (revenue / 12) if revenue else None
        result.append(
            {
                **base,
                "product_code": candidate["product_code"],
                "cand_amount": cand_amount,
                "cand_term": candidate["term_months"],
                "cand_rate": float(candidate["rate"]),
                "cand_payment": payment,
                "amount_ratio": cand_amount / amount,
                "term_delta": candidate["term_months"] - request["term_requested"],
                "purpose_match": int(
                    request["purpose"] in products[candidate["product_code"]]["purpose_tags"]
                ),
                "dti": dti,
                "dti_bucket": bucket(dti, (0.25, 0.35, 0.50)) if dti is not None else None,
                "pre_score": score.total,
                "pre_grade": score.grade or "UNKNOWN",
                "rule_hint": decision.rule,
            }
        )
    return result


def build_features(request, candidates, *, company, fns, bki, config, engine) -> pd.DataFrame:
    """Stable ordered schema. No identifiers, positions, decisions or latent truth."""
    rows = build_feature_rows(
        request, candidates, company=company, fns=fns, bki=bki, config=config, engine=engine
    )
    return model_frame(rows, category_vocabulary(config))


def baseline_b_key(row: dict) -> tuple:
    dti = row["dti"]
    affordable = dti is not None and math.isfinite(dti) and dti <= 0.35
    # Normalized absolute distance prevents rubles overwhelming months.
    distance = abs(1 - row["amount_ratio"]) + abs(row["term_delta"]) / max(1, row["term_requested"])
    return (not affordable, distance, row["cand_payment"])


def baseline_c_key(row: dict) -> tuple:
    hint = row["rule_hint"]
    priority = 0 if hint == "R9" else 1 if hint in {"R3", "R5", "R7", "BKI_REQUIRED"} else 2
    return (priority, *baseline_b_key(row))

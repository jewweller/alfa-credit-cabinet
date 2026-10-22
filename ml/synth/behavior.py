"""Choice with an outside option, examination bias and a causal application funnel."""

import math

import numpy as np
from scipy.special import expit

from .features import baseline_b_key
from .population import weighted


def utility(row: dict, latent: dict, cfg: dict) -> float:
    burden = (
        row["dti"]
        if row["dti"] is not None
        else (
            (row["existing_payments_monthly"] + row["cand_payment"])
            / (row["amount_requested"] / row["amount_to_revenue"] / 12)
        )
    )
    term_distance = abs(
        row["cand_term"] / max(row["term_requested"], 1) - latent["term_preference"]
    )
    shortage = max(0, 1 - row["amount_ratio"])
    return (
        cfg["utility_intercept"]
        - cfg["dti_penalty"] * burden * latent["price_sensitivity"]
        - cfg["rate_penalty"] * row["cand_rate"] / 20 * latent["price_sensitivity"]
        - cfg["term_penalty"] * term_distance
        - cfg["shortage_penalty"] * shortage * (1 - latent["amount_flexibility"])
        + cfg["purpose_bonus"] * row["purpose_match"]
    )


def acceptance_probability(candidate, offer, latent, cfg):
    offer = offer or candidate
    change = abs(float(offer["amount"]) / float(candidate["amount"]) - 1)
    change += abs(offer["term_months"] / candidate["term_months"] - 1)
    return float(
        expit(
            cfg["acceptance_intercept"]
            - cfg["acceptance_rate_penalty"]
            * float(offer["rate"])
            / 20
            * latent["price_sensitivity"]
            - cfg["acceptance_change_penalty"] * change * (1 - latent["amount_flexibility"])
        )
    )


def approval_probability(decision, row, latent, cfg):
    if decision.outcome == "rejected":
        return 0.0
    if decision.outcome in {"approved", "counter_offer"}:
        return 1.0
    dti = row["dti"] or 0
    return float(
        np.clip(
            cfg["manual_approval_base"]
            - cfg["manual_risk_penalty"] * latent["latent_risk"]
            - cfg["manual_dti_penalty"] * max(0, dti - 0.35),
            0,
            1,
        )
    )


def relevance(
    *,
    shown: bool,
    random_policy: bool,
    clicked: bool,
    applied: bool,
    final_outcome: str | None,
    offer_accepted: bool,
    issued: bool,
) -> int | None:
    if not shown:
        return 0 if random_policy else None
    if issued:
        return 4
    if offer_accepted:
        return 3
    if applied:
        return 2 if final_outcome in {"approved", "counter_offer"} else 0
    return int(clicked)


def simulate_funnel(request, candidates, features, decisions, latent, config, rng):
    cfg = config["behavior"]
    random_policy = bool(rng.random() < config["display"]["random_probability"])
    order = (
        rng.permutation(len(candidates)).tolist()
        if random_policy
        else sorted(
            range(len(candidates)),
            key=lambda i: (baseline_b_key(features[i]), candidates[i]["candidate_id"]),
        )
    )
    count = min(len(order), weighted(rng, config["display"]["shown_count"]))
    shown = order[:count]
    for position, i in enumerate(shown, 1):
        candidates[i]["shown_position"] = position
    utilities = [utility(row, latent, cfg) for row in features]
    # Gumbel-max is multinomial logit; include the explicit "nothing" option.
    values = [utilities[i] for i in shown] + [cfg["outside_utility"]]
    picked = int(np.argmax(np.asarray(values) + rng.gumbel(0, cfg["gumbel_scale"], len(values))))
    selected = shown[picked] if picked < len(shown) else None
    if selected is not None:
        examination = (
            1
            / math.log2(candidates[selected]["shown_position"] + 1)
            ** config["display"]["examination_exponent"]
        )
        if rng.random() >= examination:
            selected = None
    outcomes, truth = [], []
    for i, (candidate, row, decision) in enumerate(
        zip(candidates, features, decisions, strict=True)
    ):
        approve = approval_probability(decision, row, latent, cfg)
        accept = acceptance_probability(candidate, decision.offer, latent, cfg)
        clicked = selected == i
        applied = (
            clicked
            and rng.random()
            < cfg["application_base"] + cfg["application_urgency"] * latent["urgency"]
        )
        final = decision.outcome if applied else None
        reason = decision.reason_code if applied else None
        if applied and final in {"manual_review", "info_requested"}:
            final = "approved" if rng.random() < approve else "rejected"
            reason = None if final == "approved" else "underwriter_decision"
        accepted = bool(
            applied and final in {"approved", "counter_offer"} and rng.random() < accept
        )
        issued = accepted and rng.random() < cfg["issuance_probability"]
        label = relevance(
            shown=candidate["shown_position"] is not None,
            random_policy=random_policy,
            clicked=clicked,
            applied=bool(applied),
            final_outcome=final,
            offer_accepted=accepted,
            issued=bool(issued),
        )
        outcomes.append(
            {
                "request_id": request["request_id"],
                "candidate_id": candidate["candidate_id"],
                "clicked": clicked,
                "applied": bool(applied),
                "decision_outcome": decision.outcome,
                "rule": decision.rule,
                "reason_code": decision.reason_code,
                "final_outcome": final,
                "final_reason_code": reason,
                "offer": decision.offer,
                "offer_accepted": accepted,
                "issued": bool(issued),
                "label": label,
            }
        )
        truth.append(
            {
                "request_id": request["request_id"],
                "company_id": request["company_id"],
                "candidate_id": candidate["candidate_id"],
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
                "approval_probability": approve,
                "acceptance_probability": accept,
                "client_utility": utilities[i],
                "ideal_relevance": approve * accept * float(expit(utilities[i])),
            }
        )
    return outcomes, truth, random_policy

"""Observable candidate generation: never consult future BKI without consent."""

from .features import baseline_b_key, build_feature_rows
from .money import maximum_amount, money, monthly_payment
from .rules import existing_payments, hard_filter, latest_revenue, visible_bki


def generate_candidates(company, request, fns, bki, config, engine, new_id):
    bureau = visible_bki(request, bki)
    stop = hard_filter(company, bureau)
    if stop:
        return [], stop
    cc = config["candidates"]
    terms = sorted({request["term_requested"] + delta for delta in cc["term_offsets"]})
    revenue, _ = latest_revenue(fns)
    revenue = revenue or float(request["revenue_12m"])
    budget = revenue / 12 * config["rules"]["dti_limit"] - existing_payments(request, bureau)
    rows = []
    for product in config["products"]:
        for term in terms:
            if not product["min_term"] <= term <= product["max_term"]:
                continue
            amounts = {
                money(float(request["amount_requested"]) * share)
                for share in cc["amount_fractions"]
            }
            # Conservative spread removes the rate/amount/grade circular dependency.
            amounts.add(
                maximum_amount(
                    budget, float(product["base_rate"]) + 4, term, float(product["max_amount"])
                )
            )
            for amount in sorted(amounts, key=float):
                if (
                    not float(product["min_amount"])
                    <= float(amount)
                    <= float(product["max_amount"])
                ):
                    continue
                candidate = {
                    "request_id": request["request_id"],
                    "candidate_id": new_id(),
                    "product_code": product["code"],
                    "amount": amount,
                    "term_months": term,
                }
                grade = engine.score(company, request, candidate, fns, bureau).grade
                grade = grade or cc["unknown_grade_for_pricing"]
                rate = money(float(product["base_rate"]) + config["rules"]["rate_spreads"][grade])
                candidate.update(
                    rate=rate,
                    monthly_payment=monthly_payment(amount, rate, term),
                    shown_position=None,
                )
                rows.append(candidate)
    if len(rows) > cc["max_candidates"]:
        features = build_feature_rows(
            request, rows, company=company, fns=fns, bki=bki, config=config, engine=engine
        )
        # Keep the closest half and a deterministic spread of the remaining grid.
        # No outcome, hidden risk or display-policy randomness influences this cap.
        ranked = sorted(
            range(len(rows)), key=lambda i: (baseline_b_key(features[i]), rows[i]["candidate_id"])
        )
        keep = cc["max_candidates"] // 2
        remainder = ranked[keep:]
        n = cc["max_candidates"] - keep
        chosen = ranked[:keep] + [remainder[i * len(remainder) // n] for i in range(n)]
        rows = [rows[i] for i in sorted(chosen)]
    return rows, None if rows else "product_limits"

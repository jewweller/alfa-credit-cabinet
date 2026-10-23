from copy import deepcopy
from itertools import count

import pandas as pd
import pytest
from ml.synth.candidates import generate_candidates
from ml.synth.features import CATEGORICAL, FEATURES, build_features
from ml.synth.ranking import rank_candidates


def build(demo, config):
    company, request, candidate, fns, bki, engine = demo
    return build_features(
        request, [candidate], company=company, fns=fns, bki=bki, config=config, engine=engine
    )


def test_no_bki_leakage_even_if_hidden_report_is_passed(demo, config):
    company, request, candidate, fns, bki, engine = demo
    request["bki_consent"] = False
    before = build(demo, config)
    bki.update(
        bankruptcy=True,
        max_overdue_days_24m=999,
        current_overdue_days=999,
        inquiries_30d=999,
        loans=[{"monthly_payment": "999999.00"}],
    )
    after = build(demo, config)
    pd.testing.assert_frame_equal(before, after)
    assert all(after[name].isna().all() for name in FEATURES if name.startswith("bki_"))
    assert after.pre_grade.iloc[0] == "UNKNOWN"
    assert after.pre_score.iloc[0] == 75
    assert after.existing_payments_monthly.iloc[0] == 150000


def test_unavailable_fns_is_missing_not_zero(demo, config):
    demo[3]["available"] = False
    frame = build(demo, config)
    for field in (
        "revenue_last",
        "revenue_growth",
        "revenue_mismatch",
        "tax_debt_bucket",
        "risk_flags_count",
        "dti",
        "dti_bucket",
    ):
        assert frame[field].isna().all()
    assert frame.rule_hint.iloc[0] == "R3"


def test_allowlist_types_and_identifier_independence(demo, config):
    before = build(demo, config)
    demo[0]["company_id"] = "unseen-company"
    demo[0]["inn"] = "secret"
    demo[1]["request_id"] = "new-qid"
    demo[2].update(candidate_id="new-id", shown_position=99, issued=True, latent_risk=0.9)
    pd.testing.assert_frame_equal(before, build(demo, config))
    assert list(before) == list(FEATURES)
    assert all(isinstance(before[name].dtype, pd.CategoricalDtype) for name in CATEGORICAL)
    assert not set(FEATURES) & {
        "candidate_id",
        "company_id",
        "inn",
        "request_id",
        "shown_position",
        "latent_risk",
        "clicked",
        "applied",
        "label",
        "reason_code",
    }


def test_preliminary_hint_does_not_use_unknown_f2(demo, config):
    demo[1]["bki_consent"] = False
    assert build(demo, config).rule_hint.iloc[0] == "BKI_REQUIRED"
    demo[1]["bki_consent"] = True
    demo[4]["available"] = False
    assert build(demo, config).rule_hint.iloc[0] == "R3"


def test_filter_and_grid_use_only_observed_information(demo, config):
    company, request, candidate, fns, bki, engine = demo
    seq = count()

    def generate():
        return generate_candidates(
            company, request, fns, bki, config, engine, lambda: str(next(seq))
        )

    rows, reason = generate()
    assert reason is None and 6 <= len(rows) <= 20
    assert len({(r["product_code"], r["amount"], r["term_months"]) for r in rows}) == len(rows)
    for row in rows:
        product = engine.products[row["product_code"]]
        assert float(product["min_amount"]) <= float(row["amount"]) <= float(product["max_amount"])
        assert product["min_term"] <= row["term_months"] <= product["max_term"]
    bki["bankruptcy"] = True
    assert generate() == ([], "R2")
    request["bki_consent"] = False
    assert len(generate()[0]) > 0
    company["status"] = "LIQUIDATING"
    assert generate() == ([], "R1")


def test_fallback_with_disabled_or_missing_model(demo, config, tmp_path):
    company, request, candidate, fns, bki, engine = demo
    second = deepcopy(candidate)
    second.update(candidate_id="second", amount="1500000.00", monthly_payment="137519.99")
    kwargs = dict(company=company, fns=fns, bki=bki, config=config, engine=engine)
    result = rank_candidates(request, [second, candidate], **kwargs)
    assert result[0]["candidate_id"] == candidate["candidate_id"]
    assert (
        rank_candidates(
            request, [second, candidate], enabled=True, model_directory=tmp_path, **kwargs
        )
        == result
    )


@pytest.mark.parametrize("consent", [True, False])
def test_hidden_report_cannot_change_candidate_set_without_consent(demo, config, consent):
    company, request, candidate, fns, bki, engine = demo
    request["bki_consent"] = consent

    def generate():
        ids = count()
        return generate_candidates(
            company, request, fns, bki, config, engine, lambda: str(next(ids))
        )[0]

    before = generate()
    bki["bankruptcy"] = True
    assert (generate() == before) is (not consent)

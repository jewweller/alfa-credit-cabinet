from dataclasses import replace

import numpy as np
import pytest
from ml.synth.behavior import acceptance_probability, approval_probability, relevance, utility
from ml.synth.features import build_feature_rows
from ml.synth.rules import Decision


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, 0),
        ({"clicked": True}, 1),
        ({"clicked": True, "applied": True, "final_outcome": "rejected"}, 0),
        ({"clicked": True, "applied": True, "final_outcome": "approved"}, 2),
        ({"clicked": True, "applied": True, "final_outcome": "counter_offer"}, 2),
        ({"clicked": True, "applied": True, "offer_accepted": True}, 3),
        ({"clicked": True, "applied": True, "offer_accepted": True, "issued": True}, 4),
        ({"shown": False}, None),
        ({"shown": False, "random_policy": True}, 0),
    ],
)
def test_funnel_labels(overrides, expected):
    params = dict(
        shown=True,
        random_policy=False,
        clicked=False,
        applied=False,
        final_outcome=None,
        offer_accepted=False,
        issued=False,
    )
    assert relevance(**(params | overrides)) == expected


def test_structural_behavior_signs(config, demo):
    company, request, candidate, fns, bki, engine = demo
    row = build_feature_rows(
        request, [candidate], company=company, fns=fns, bki=bki, config=config, engine=engine
    )[0]
    latent = dict(latent_risk=0.5, price_sensitivity=1, term_preference=1, amount_flexibility=0.5)
    cfg = config["behavior"]
    assert utility(row | {"dti": 0.8}, latent, cfg) < utility(row | {"dti": 0.2}, latent, cfg)
    assert acceptance_probability(
        candidate, candidate | {"rate": "24.00"}, latent, cfg
    ) < acceptance_probability(candidate, candidate | {"rate": "18.00"}, latent, cfg)
    manual = Decision("manual_review", "R7")
    assert approval_probability(manual, row | {"dti": 0.8}, latent, cfg) < approval_probability(
        manual, row | {"dti": 0.2}, latent, cfg
    )
    assert approval_probability(replace(manual, outcome="rejected"), row, latent, cfg) == 0


def test_gumbel_max_matches_multinomial_logit():
    rng = np.random.default_rng(17)
    utilities = np.array([0.0, 0.5, 1.5])
    choices = np.argmax(utilities + rng.gumbel(size=(30000, 3)), axis=1)
    expected = np.exp(utilities) / np.exp(utilities).sum()
    np.testing.assert_allclose(np.bincount(choices) / len(choices), expected, atol=0.012)

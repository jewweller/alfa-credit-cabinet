import copy
import math

import pytest
from app.schemas.ml import FeedRankRequest
from ml.synth.features import FEATURES, features, revenue_growth


def test_known_example_features(payload):
    values = dict(
        zip(
            FEATURES,
            features(payload["profile"], payload["candidates"][0], payload["now"]),
            strict=True,
        )
    )
    assert len(values) == 20
    assert values["m_okved"] == values["m_product"] == values["m_segment"] == 1
    assert values["action_needed"] == values["product_known"] == 1
    assert values["no_apps"] == values["young"] == values["micro"] == 0
    assert values["growth"] == pytest.approx(0.12, abs=1e-6)
    assert 0 < values["fresh_7d"] < 1
    assert values["topic_industry"] == 1


@pytest.mark.parametrize(
    ("revenue", "expected"),
    [
        ({}, 0),
        ({"2025": 10}, 0),
        ({"2024": 0, "2025": 10}, 0),
        ({"2024": 10, "2025": 100}, 1),
        ({"2024": 10, "2025": 0}, -1),
        ({"2025": 20, "2024": 10}, 1),
    ],
)
def test_revenue_boundaries(revenue, expected):
    assert revenue_growth(revenue) == expected


def test_json_and_backend_python_payload_have_identical_features(payload):
    parsed = FeedRankRequest.model_validate(payload).model_dump()
    assert features(parsed["profile"], parsed["candidates"][0], parsed["now"]) == features(
        payload["profile"], payload["candidates"][0], payload["now"]
    )


def test_labels_ids_text_and_rule_score_do_not_enter_features(payload):
    candidate = payload["candidates"][0]
    original = features(payload["profile"], candidate, payload["now"])
    changed = copy.deepcopy(candidate)
    changed.update(
        id="another-id",
        title="changed",
        body="changed",
        rule_score=100,
        click=1,
        p_interest=0.99,
        request_id=100,
    )
    assert features(payload["profile"], changed, payload["now"]) == original


def test_future_naive_date_and_missing_data_are_finite(payload):
    payload["profile"].update(
        revenue={}, applications=[{"status": "DRAFT", "product_code": None, "purpose": None}]
    )
    candidate = payload["candidates"][0]
    candidate["published_at"] = "2027-01-01T00:00:00"
    result = features(payload["profile"], candidate, "2026-10-24T12:00:00+03:00")
    assert all(math.isfinite(v) for v in result)
    assert result[FEATURES.index("fresh_7d")] == 1

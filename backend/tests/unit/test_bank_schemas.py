import pytest
from pydantic import ValidationError

from app.schemas.bank import UnderwriterDecisionRequest

PRODUCT = "7f1c2b0a-0000-4000-8000-000000000001"
TAX_RETURN = {"kind": "tax_return", "title": "Декларация за 2025 год", "required": True}

# Для каждого исхода B4 — минимально достаточное тело (план, раздел 11).
VALID = {
    "approved": {"rate": "20.00"},
    "counter_offer": {
        "product_id": PRODUCT,
        "amount": "1500000.00",
        "term_months": 24,
        "rate": "20.00",
    },
    "info_requested": {"info_items": [TAX_RETURN], "comment": "Подтвердите выручку"},
    "rejected": {"reason_code": "underwriter_decision"},
}


@pytest.mark.parametrize("outcome", VALID)
def test_minimal_body_per_outcome_is_valid(outcome: str) -> None:
    UnderwriterDecisionRequest.model_validate({"outcome": outcome, **VALID[outcome]})


@pytest.mark.parametrize(
    ("outcome", "missing"),
    [(outcome, field) for outcome, body in VALID.items() for field in body],
)
def test_each_required_field_per_outcome(outcome: str, missing: str) -> None:
    body = {key: value for key, value in VALID[outcome].items() if key != missing}
    with pytest.raises(ValidationError, match=missing):
        UnderwriterDecisionRequest.model_validate({"outcome": outcome, **body})


def test_info_request_needs_at_least_one_item() -> None:
    with pytest.raises(ValidationError, match="info_items"):
        UnderwriterDecisionRequest.model_validate(
            {"outcome": "info_requested", "info_items": [], "comment": "Подтвердите выручку"}
        )


def test_manual_review_is_not_an_underwriter_outcome() -> None:
    with pytest.raises(ValidationError):
        UnderwriterDecisionRequest.model_validate({"outcome": "manual_review"})

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.state_machine import ApplicationStatus
from app.schemas.applications import ApplicationCreate, ApplicationSummary, ApplicationUpdate
from app.schemas.auth import LoginRequest
from app.schemas.companies import CompanyLookupResponse
from app.schemas.decisions import REJECT_REASON_DESCRIPTIONS, RejectReason
from app.schemas.documents import MAX_UPLOAD_BYTES, DocumentInfo
from app.schemas.products import Product, ProductRecommendRequest
from app.schemas.schedule import PaymentScheduleItem


def _product(**overrides: object) -> Product:
    data = {
        "id": uuid4(),
        "code": "EXPRESS_WC",
        "name": "Экспресс-оборот",
        "purpose_tags": ["working_capital"],
        "min_amount": "300000.00",
        "max_amount": "5000000.00",
        "min_term": 3,
        "max_term": 24,
        "base_rate": "18.00",
    }
    return Product.model_validate({**data, **overrides})


def test_money_and_rate_parse_from_strings_and_serialize_back() -> None:
    product = _product()

    assert product.max_amount == Decimal("5000000.00")
    assert product.base_rate == Decimal("18.00")
    dumped = product.model_dump(mode="json")
    assert dumped["max_amount"] == "5000000.00"
    assert dumped["base_rate"] == "18.00"


@pytest.mark.parametrize(
    "value", [5000000, 5000000.0, "5000000", "5000000.5", "5000000.000", "-1.00"]
)
def test_money_rejects_numbers_and_wrong_precision(value: object) -> None:
    with pytest.raises(ValidationError):
        _product(max_amount=value)


def _summary(amount: Decimal) -> ApplicationSummary:
    return ApplicationSummary(
        id=uuid4(),
        number="A-1",
        status=ApplicationStatus.DRAFT,
        product_id=None,
        amount=amount,
        term_months=12,
        submitted_at=None,
        status_changed_at=datetime.now(UTC),
        info_request=None,
    )


def test_money_from_decimal_serializes_with_two_digits() -> None:
    assert _summary(Decimal("275040")).model_dump(mode="json")["amount"] == "275040.00"


def test_money_does_not_round_silently() -> None:
    # Правило округления в плане не задано — значение с долями копейки отклоняется.
    with pytest.raises(ValidationError):
        _summary(Decimal("275039.985"))


def test_application_update_requires_version() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ApplicationUpdate.model_validate({"amount": "3000000.00"})

    assert exc_info.value.errors()[0]["loc"] == ("version",)


def test_application_update_accepts_partial_fields() -> None:
    update = ApplicationUpdate.model_validate({"version": 1, "term_months": 12})

    assert update.model_dump(exclude_unset=True) == {"version": 1, "term_months": 12}


@pytest.mark.parametrize(
    "model", [ApplicationCreate, ApplicationUpdate, LoginRequest, ProductRecommendRequest]
)
def test_request_models_reject_unknown_fields(model: type) -> None:
    base = {"version": 1} if model is ApplicationUpdate else {}
    if model is LoginRequest:
        base = {"email": "bakery@demo.local", "password": "x"}
    if model is ProductRecommendRequest:
        base = {"purpose": "working_capital", "amount": "3000000.00", "term_months": 12}

    with pytest.raises(ValidationError):
        model.model_validate({**base, "unexpected": True})


def test_application_create_has_no_company_field_yet() -> None:
    # Источник компании заявки — открытый вопрос (TBD), поле пока не фиксируем.
    assert "company_id" not in ApplicationCreate.model_fields
    assert "inn" not in ApplicationCreate.model_fields


@pytest.mark.parametrize("inn", ["123", "77010000190", "770100001a"])
def test_company_lookup_rejects_malformed_inn(inn: str) -> None:
    with pytest.raises(ValidationError):
        CompanyLookupResponse.model_validate(
            {
                "inn": inn,
                "kind": "LLC",
                "ogrn": "1",
                "name": "x",
                "status": "ACTIVE",
                "registered_at": "2019-01-01",
                "okved_main": "10.71",
                "region": "77",
            }
        )


def test_every_reject_reason_has_explanation() -> None:
    assert set(REJECT_REASON_DESCRIPTIONS) == set(RejectReason)
    assert all(text.strip() for text in REJECT_REASON_DESCRIPTIONS.values())


def _document(size: int) -> DocumentInfo:
    return DocumentInfo.model_validate(
        {
            "id": uuid4(),
            "kind": "tax_return",
            "filename": "declaration.pdf",
            "mime": "application/pdf",
            "size_bytes": size,
            "info_request_id": None,
            "uploaded_at": "2026-10-22T10:00:00Z",
        }
    )


def test_document_size_is_limited_to_10_mb() -> None:
    assert _document(MAX_UPLOAD_BYTES).size_bytes == MAX_UPLOAD_BYTES
    with pytest.raises(ValidationError):
        _document(MAX_UPLOAD_BYTES + 1)


def test_schedule_item_money_serializes_as_strings() -> None:
    item = PaymentScheduleItem(
        number=1,
        due_date="2026-11-22",
        payment=Decimal("275040.00"),
        principal=Decimal("230040.00"),
        interest=Decimal("45000.00"),
        balance=Decimal("2769960.00"),
    )
    dumped = item.model_dump(mode="json")
    assert dumped["payment"] == "275040.00"
    assert dumped["balance"] == "2769960.00"

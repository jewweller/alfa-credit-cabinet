import pytest
from ml.synth.config import load_config
from ml.synth.generate import generate
from ml.synth.money import monthly_payment
from ml.synth.rules import PlanRules


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def demo(config):
    company = {
        "company_id": "demo",
        "kind": "LLC",
        "status": "ACTIVE",
        "registered_at": "2019-10-22",
        "okved_main": "10.71",
        "region": "77",
        "segment": "micro",
        "employees": 10,
    }
    request = {
        "request_id": "demo-request",
        "company_id": "demo",
        "created_at": "2026-10-22T12:00:00+00:00",
        "purpose": "working_capital",
        "amount_requested": "3000000.00",
        "term_requested": 12,
        "revenue_12m": "24000000.00",
        "existing_payments_monthly": "150000.00",
        "bki_consent": True,
    }
    fns = {
        "available": True,
        "revenue": {"2024": "21428571.43", "2025": "24000000.00"},
        "tax_debt_rub": "0.00",
        "flags": {"mass_address": False, "unreliable_address": False, "unreliable_director": False},
    }
    bki = {
        "available": True,
        "has_history": True,
        "bankruptcy": False,
        "max_overdue_days_24m": 0,
        "current_overdue_days": 0,
        "inquiries_30d": 0,
        "loans": [{"monthly_payment": "150000.00"}],
    }
    candidate = {
        "candidate_id": "demo-candidate",
        "product_code": "EXPRESS_WC",
        "amount": "3000000.00",
        "term_months": 12,
        "rate": "18.00",
        "monthly_payment": monthly_payment("3000000.00", "18.00", 12),
    }
    return company, request, candidate, fns, bki, PlanRules(config)


@pytest.fixture(scope="session")
def run(tmp_path_factory):
    return generate(load_config(), 42, tmp_path_factory.mktemp("dataset"), companies=200)

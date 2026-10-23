import json
from datetime import date
from decimal import Decimal

import pytest

from app.config import get_settings
from app.integrations.base import SOURCES, FetchResult
from app.integrations.fixtures import FixtureSourceClient
from app.integrations.parsing import to_applicant_sources
from app.scoring.inputs import SourceState

FIXTURES = get_settings().fixtures_dir

# Поля ответов по контрактам моков (docs/plan.md, раздел 8).
CONTRACT_FIELDS = {
    "egrul": {
        "inn", "ogrn", "name", "status", "registered_at", "okved_main", "okved_extra",
        "director", "founders", "address", "region",
    },
    "egrip": {"inn", "ogrnip", "fio", "status", "registered_at", "okved_main", "region"},
    "fns_tb": {"revenue", "tax_debt_rub", "msp_category", "employees", "flags"},
    "bki": {"report_id", "has_history", "bankruptcy", "loans", "inquiries_30d"},
}  # fmt: skip
LOAN_FIELDS = {"type", "balance", "monthly_payment", "max_overdue_days_24m", "current_overdue_days"}


@pytest.mark.parametrize("source", SOURCES)
def test_fixtures_follow_mock_contract_and_cite_sources(source: str) -> None:
    raw = json.loads((FIXTURES / f"{source}.json").read_text(encoding="utf-8"))

    assert raw["_meta"]["status"].startswith("draft")
    for inn, entry in ((k, v) for k, v in raw.items() if not k.startswith("_")):
        assert set(entry["response"]) == CONTRACT_FIELDS[source], inn
        assert entry["sources"], f"{source}/{inn}: нет происхождения значений"
        for loan in entry["response"].get("loans", []):
            assert set(loan) == LOAN_FIELDS


@pytest.fixture(scope="module")
def sources() -> FixtureSourceClient:
    return FixtureSourceClient(FIXTURES)


def test_known_inn_returns_contract_response(sources: FixtureSourceClient) -> None:
    result = sources.fetch("egrul", "7701000019")

    assert result.state == SourceState.OK
    assert result.payload["status"] == "ACTIVE"
    assert "sources" not in result.payload


def test_missing_registry_entry_is_not_found(sources: FixtureSourceClient) -> None:
    assert sources.fetch("egrul", "7701000072").state == SourceState.NOT_FOUND


def test_missing_fns_or_bki_entry_is_unavailable(sources: FixtureSourceClient) -> None:
    assert sources.fetch("fns_tb", "7701000026").state == SourceState.UNAVAILABLE
    assert sources.fetch("bki", "7701000026").state == SourceState.UNAVAILABLE


def test_parsing_bakery_responses(sources: FixtureSourceClient) -> None:
    results = {s: sources.fetch(s, "7701000019") for s in ("egrul", "fns_tb", "bki")}

    applicant = to_applicant_sources("LLC", results)

    assert applicant.registry.data.registered_at == date(2018, 9, 14)
    assert applicant.fns.data.revenue_by_year == {2024: Decimal(21428571), 2025: Decimal(24000000)}
    assert applicant.bki.data.loans[0].monthly_payment == Decimal(150000)


def test_parsing_keeps_source_states() -> None:
    results = {
        "egrip": FetchResult("egrip", SourceState.NOT_FOUND),
        "fns_tb": FetchResult("fns_tb", SourceState.UNAVAILABLE),
        "bki": FetchResult("bki", SourceState.UNAVAILABLE),
    }

    applicant = to_applicant_sources("IE", results)

    assert applicant.registry.state == SourceState.NOT_FOUND
    assert applicant.fns.data is None and applicant.bki.data is None


def test_malformed_response_raises_instead_of_guessing() -> None:
    results = {
        "egrul": FetchResult("egrul", SourceState.OK, {"status": "ACTIVE"}),  # нет registered_at
        "fns_tb": FetchResult("fns_tb", SourceState.UNAVAILABLE),
        "bki": FetchResult("bki", SourceState.UNAVAILABLE),
    }

    with pytest.raises(KeyError):
        to_applicant_sources("LLC", results)

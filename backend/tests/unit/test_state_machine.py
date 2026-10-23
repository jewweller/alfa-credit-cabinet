"""Матрица переходов сверяется с диаграммой из плана (раздел 5), а не с самим модулем."""

from itertools import product

import pytest

from app.domain.state_machine import (
    TERMINAL_STATUSES,
    TRANSITIONS,
    ApplicationStatus,
    InvalidTransitionError,
    can_transition,
    ensure_transition,
)

S = ApplicationStatus

# Рёбра mermaid-диаграммы из docs/plan.md, раздел 5 (без [*]) — 21 штука.
PLAN_EDGES: set[tuple[ApplicationStatus, ApplicationStatus]] = {
    (S.DRAFT, S.SUBMITTED),
    (S.DRAFT, S.CANCELLED),
    (S.SUBMITTED, S.ENRICHMENT),
    (S.ENRICHMENT, S.SCORING),
    (S.SCORING, S.APPROVED),
    (S.SCORING, S.COUNTER_OFFER),
    (S.SCORING, S.REJECTED),
    (S.SCORING, S.INFO_REQUESTED),
    (S.SCORING, S.MANUAL_REVIEW),
    (S.MANUAL_REVIEW, S.APPROVED),
    (S.MANUAL_REVIEW, S.COUNTER_OFFER),
    (S.MANUAL_REVIEW, S.REJECTED),
    (S.MANUAL_REVIEW, S.INFO_REQUESTED),
    (S.INFO_REQUESTED, S.SUBMITTED),
    (S.INFO_REQUESTED, S.CANCELLED),
    (S.APPROVED, S.SIGNING),
    (S.COUNTER_OFFER, S.SIGNING),
    (S.APPROVED, S.DECLINED_BY_CLIENT),
    (S.COUNTER_OFFER, S.DECLINED_BY_CLIENT),
    (S.SIGNING, S.SIGNED),
    (S.SIGNED, S.ISSUED),
}

ALL_PAIRS = list(product(ApplicationStatus, repeat=2))


def test_plan_has_14_statuses_and_all_are_described() -> None:
    assert len(ApplicationStatus) == 14
    assert len(PLAN_EDGES) == 21
    assert set(TRANSITIONS) == set(ApplicationStatus)


@pytest.mark.parametrize(("from_status", "to_status"), ALL_PAIRS)
def test_full_matrix_matches_plan(
    from_status: ApplicationStatus, to_status: ApplicationStatus
) -> None:
    expected = (from_status, to_status) in PLAN_EDGES

    assert can_transition(from_status, to_status) is expected


def test_terminal_statuses_match_plan() -> None:
    expected = {S.REJECTED, S.ISSUED, S.CANCELLED, S.DECLINED_BY_CLIENT}

    assert expected == TERMINAL_STATUSES


def test_ensure_transition_allows_valid_edge() -> None:
    ensure_transition(S.DRAFT, S.SUBMITTED)


def test_ensure_transition_rejects_invalid_edge() -> None:
    with pytest.raises(InvalidTransitionError) as exc_info:
        ensure_transition(S.DRAFT, S.APPROVED)

    assert exc_info.value.from_status is S.DRAFT
    assert exc_info.value.to_status is S.APPROVED

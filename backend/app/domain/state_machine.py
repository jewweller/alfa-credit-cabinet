"""Машина состояний заявки: статусы и разрешённые переходы (план, раздел 5).

Все переходы описаны только здесь. Недопустимый переход — InvalidTransitionError,
которую слой API превращает в 409 Conflict.
"""

from enum import StrEnum


class ApplicationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    ENRICHMENT = "ENRICHMENT"
    SCORING = "SCORING"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    INFO_REQUESTED = "INFO_REQUESTED"
    APPROVED = "APPROVED"
    COUNTER_OFFER = "COUNTER_OFFER"
    REJECTED = "REJECTED"
    SIGNING = "SIGNING"
    SIGNED = "SIGNED"
    ISSUED = "ISSUED"
    DECLINED_BY_CLIENT = "DECLINED_BY_CLIENT"
    CANCELLED = "CANCELLED"


S = ApplicationStatus

TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    S.DRAFT: frozenset({S.SUBMITTED, S.CANCELLED}),
    S.SUBMITTED: frozenset({S.ENRICHMENT}),
    S.ENRICHMENT: frozenset({S.SCORING}),
    S.SCORING: frozenset(
        {S.APPROVED, S.COUNTER_OFFER, S.REJECTED, S.INFO_REQUESTED, S.MANUAL_REVIEW}
    ),
    S.MANUAL_REVIEW: frozenset({S.APPROVED, S.COUNTER_OFFER, S.REJECTED, S.INFO_REQUESTED}),
    S.INFO_REQUESTED: frozenset({S.SUBMITTED, S.CANCELLED}),
    S.APPROVED: frozenset({S.SIGNING, S.DECLINED_BY_CLIENT}),
    S.COUNTER_OFFER: frozenset({S.SIGNING, S.DECLINED_BY_CLIENT}),
    S.SIGNING: frozenset({S.SIGNED}),
    S.SIGNED: frozenset({S.ISSUED}),
    S.REJECTED: frozenset(),
    S.ISSUED: frozenset(),
    S.DECLINED_BY_CLIENT: frozenset(),
    S.CANCELLED: frozenset(),
}

TERMINAL_STATUSES: frozenset[ApplicationStatus] = frozenset(
    status for status, targets in TRANSITIONS.items() if not targets
)


class InvalidTransitionError(Exception):
    def __init__(self, from_status: ApplicationStatus, to_status: ApplicationStatus) -> None:
        super().__init__(f"Переход {from_status} → {to_status} не разрешён")
        self.from_status = from_status
        self.to_status = to_status


def can_transition(from_status: ApplicationStatus, to_status: ApplicationStatus) -> bool:
    return to_status in TRANSITIONS[from_status]


def ensure_transition(from_status: ApplicationStatus, to_status: ApplicationStatus) -> None:
    if not can_transition(from_status, to_status):
        raise InvalidTransitionError(from_status, to_status)

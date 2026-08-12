from enum import StrEnum


class WorkflowStatus(StrEnum):
    RECEIVED = "received"
    QUEUED = "queued"
    VALIDATING = "validating"
    INVALID = "invalid"
    NORMALIZED = "normalized"
    RETRY_WAIT = "retry_wait"
    DEAD_LETTER = "dead_letter"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    ESCALATED = "escalated"


ALLOWED_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.RECEIVED: frozenset({WorkflowStatus.QUEUED}),
    WorkflowStatus.QUEUED: frozenset({WorkflowStatus.VALIDATING}),
    WorkflowStatus.VALIDATING: frozenset(
        {
            WorkflowStatus.NORMALIZED,
            WorkflowStatus.INVALID,
            WorkflowStatus.RETRY_WAIT,
            WorkflowStatus.DEAD_LETTER,
        }
    ),
    WorkflowStatus.RETRY_WAIT: frozenset(
        {WorkflowStatus.VALIDATING, WorkflowStatus.DEAD_LETTER}
    ),
    WorkflowStatus.DEAD_LETTER: frozenset({WorkflowStatus.QUEUED}),
    WorkflowStatus.NORMALIZED: frozenset({WorkflowStatus.PROCESSING}),
    WorkflowStatus.PROCESSING: frozenset(
        {WorkflowStatus.REVIEW_REQUIRED, WorkflowStatus.ESCALATED}
    ),
    WorkflowStatus.REVIEW_REQUIRED: frozenset(
        {WorkflowStatus.APPROVED, WorkflowStatus.ESCALATED}
    ),
    WorkflowStatus.INVALID: frozenset(),
    WorkflowStatus.APPROVED: frozenset(),
    WorkflowStatus.ESCALATED: frozenset(),
}


class InvalidTransition(ValueError):
    pass


def ensure_transition(current: WorkflowStatus, target: WorkflowStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"Workflow cannot transition from {current} to {target}")


def is_normalization_terminal(status: WorkflowStatus) -> bool:
    return status in {WorkflowStatus.NORMALIZED, WorkflowStatus.INVALID}

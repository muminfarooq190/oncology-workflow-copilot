import pytest

from app.domain import InvalidTransition, WorkflowStatus, ensure_transition
from app.repository import content_hash


def test_state_machine_allows_retry_and_manual_recovery() -> None:
    ensure_transition(WorkflowStatus.VALIDATING, WorkflowStatus.RETRY_WAIT)
    ensure_transition(WorkflowStatus.RETRY_WAIT, WorkflowStatus.VALIDATING)
    ensure_transition(WorkflowStatus.VALIDATING, WorkflowStatus.DEAD_LETTER)
    ensure_transition(WorkflowStatus.DEAD_LETTER, WorkflowStatus.QUEUED)


def test_state_machine_rejects_skipping_clinician_review() -> None:
    with pytest.raises(InvalidTransition):
        ensure_transition(WorkflowStatus.PROCESSING, WorkflowStatus.APPROVED)


def test_content_hash_is_canonical_and_contract_compatible() -> None:
    first = content_hash({"a": 1, "b": [2, 3]})
    second = content_hash({"b": [2, 3], "a": 1})

    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == 71

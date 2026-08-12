import os
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.config import Settings
from app.db import get_session_factory
from app.domain import WorkflowStatus
from app.main import app
from app.outbox import OutboxDispatcher
from app.repository import IdempotencyConflict, WorkflowService
from app.worker import WorkflowWorker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="requires PostgreSQL and Redis",
    ),
]


def synthetic_bundle(case_id: str = "case-001") -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "id": case_id,
        "meta": {
            "tag": [
                {
                    "system": "https://oncology-copilot.dev/tags",
                    "code": "synthetic",
                }
            ]
        },
        "type": "collection",
        "entry": [],
    }


def valid_result() -> dict[str, Any]:
    return {
        "validation": {
            "isValid": True,
            "fhirRelease": "R4",
            "validationLevel": "test",
            "resourceCounts": {},
            "issues": [],
        },
        "canonicalCase": {"schemaVersion": "1.0.0", "caseId": "case-001"},
    }


class StubFhirClient:
    def __init__(self, outcomes: Sequence[dict[str, Any] | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    async def normalize(self, _: dict[str, Any]) -> dict[str, Any]:
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
async def durable_context():
    suffix = uuid4().hex
    base = Settings()
    settings = base.model_copy(
        update={
            "tenant_id": f"test-{suffix}",
            "workflow_stream": f"oncology:test:{suffix}",
            "workflow_consumer_group": f"workers-{suffix}",
            "workflow_consumer_name": f"worker-{suffix}",
            "workflow_retry_delay_seconds": 0,
        }
    )
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    service = WorkflowService(get_session_factory(), settings)
    yield settings, redis, service
    await redis.delete(settings.workflow_stream)
    await redis.aclose()


@pytest.mark.asyncio
async def test_intake_is_idempotent_and_conflicts_on_changed_input(durable_context) -> None:
    _, _, service = durable_context
    key = f"case-{uuid4().hex}"
    first, created = await service.intake(
        bundle=synthetic_bundle(),
        idempotency_key=key,
        trace_id="trace-intake",
        actor_subject="test",
        actor_role="system",
    )
    replay, replay_created = await service.intake(
        bundle=synthetic_bundle(),
        idempotency_key=key,
        trace_id="trace-replay",
        actor_subject="test",
        actor_role="system",
    )

    assert created is True
    assert replay_created is False
    assert first.id == replay.id
    assert WorkflowStatus(first.status) == WorkflowStatus.QUEUED
    assert [event.action for event in await service.audit_events(first.id)] == [
        "workflow.received",
        "workflow.queued",
    ]

    with pytest.raises(IdempotencyConflict):
        await service.intake(
            bundle=synthetic_bundle("changed"),
            idempotency_key=key,
            trace_id="trace-conflict",
            actor_subject="test",
            actor_role="system",
        )


@pytest.mark.asyncio
async def test_outbox_worker_normalizes_once_under_duplicate_delivery(durable_context) -> None:
    settings, redis, service = durable_context
    workflow, _ = await service.intake(
        bundle=synthetic_bundle(),
        idempotency_key=f"case-{uuid4().hex}",
        trace_id="trace-normalize",
        actor_subject="test",
        actor_role="system",
    )
    dispatcher = OutboxDispatcher(get_session_factory(), redis, settings)
    assert await dispatcher.dispatch_batch() == 1
    entries = await redis.xrange(settings.workflow_stream)
    message_id, fields = entries[0]

    fhir = StubFhirClient([valid_result()])
    worker = WorkflowWorker(redis, service, fhir, settings)  # type: ignore[arg-type]
    await worker.ensure_consumer_group()
    assert await worker.read_once(block_milliseconds=10) == 1

    completed = await service.get(workflow.id)
    assert WorkflowStatus(completed.status) == WorkflowStatus.NORMALIZED
    assert completed.attempts == 1
    audit_count = len(await service.audit_events(workflow.id))

    await worker.process_message(message_id, fields)
    assert len(await service.audit_events(workflow.id)) == audit_count
    assert fhir.calls == 1


@pytest.mark.asyncio
async def test_transient_failures_retry_to_budget_then_succeed(durable_context) -> None:
    settings, redis, service = durable_context
    workflow, _ = await service.intake(
        bundle=synthetic_bundle(),
        idempotency_key=f"case-{uuid4().hex}",
        trace_id="trace-retry",
        actor_subject="test",
        actor_role="system",
    )
    dispatcher = OutboxDispatcher(get_session_factory(), redis, settings)
    fhir = StubFhirClient(
        [RuntimeError("temporary-1"), RuntimeError("temporary-2"), valid_result()]
    )
    worker = WorkflowWorker(redis, service, fhir, settings)  # type: ignore[arg-type]
    await worker.ensure_consumer_group()

    for _ in range(3):
        assert await dispatcher.dispatch_batch() == 1
        assert await worker.read_once(block_milliseconds=10) == 1

    completed = await service.get(workflow.id)
    assert WorkflowStatus(completed.status) == WorkflowStatus.NORMALIZED
    assert completed.attempts == 3
    assert fhir.calls == 3


@pytest.mark.asyncio
async def test_dead_letter_can_be_manually_requeued(durable_context) -> None:
    settings, redis, _ = durable_context
    settings = settings.model_copy(update={"workflow_max_attempts": 1})
    service = WorkflowService(get_session_factory(), settings)
    workflow, _ = await service.intake(
        bundle=synthetic_bundle(),
        idempotency_key=f"case-{uuid4().hex}",
        trace_id="trace-dead-letter",
        actor_subject="test",
        actor_role="system",
    )
    dispatcher = OutboxDispatcher(get_session_factory(), redis, settings)
    worker = WorkflowWorker(  # type: ignore[arg-type]
        redis, service, StubFhirClient([RuntimeError("offline")]), settings
    )
    await worker.ensure_consumer_group()
    assert await dispatcher.dispatch_batch() == 1
    assert await worker.read_once(block_milliseconds=10) == 1
    assert WorkflowStatus((await service.get(workflow.id)).status) == WorkflowStatus.DEAD_LETTER

    retried = await service.retry_dead_letter(
        workflow.id,
        trace_id="trace-manual-retry",
        actor_subject="test",
        actor_role="system",
    )
    assert WorkflowStatus(retried.status) == WorkflowStatus.QUEUED
    assert retried.attempts == 0


@pytest.mark.asyncio
async def test_database_rejects_audit_update_and_delete(durable_context) -> None:
    _, _, service = durable_context
    workflow, _ = await service.intake(
        bundle=synthetic_bundle(),
        idempotency_key=f"case-{uuid4().hex}",
        trace_id="trace-audit",
        actor_subject="test",
        actor_role="system",
    )
    for statement in (
        "UPDATE audit_events SET action = 'tampered' WHERE workflow_id = :workflow_id",
        "DELETE FROM audit_events WHERE workflow_id = :workflow_id",
    ):
        with pytest.raises(DBAPIError):
            async with get_session_factory()() as session, session.begin():
                await session.execute(text(statement), {"workflow_id": workflow.id})


@pytest.mark.asyncio
async def test_http_intake_get_and_audit_endpoints(durable_context) -> None:
    _, _, _ = durable_context
    transport = httpx.ASGITransport(app=app)
    key = f"api-{uuid4().hex}"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/v1/workflows",
            json={"fhirBundle": synthetic_bundle()},
            headers={"Idempotency-Key": key, "X-Trace-Id": "trace-api"},
        )
        replay = await client.post(
            "/v1/workflows",
            json={"fhirBundle": synthetic_bundle()},
            headers={"Idempotency-Key": key},
        )
        workflow_id = first.json()["workflowId"]
        detail = await client.get(f"/v1/workflows/{workflow_id}")
        audit = await client.get(f"/v1/workflows/{workflow_id}/audit")

    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    assert first.headers["idempotent-replay"] == "false"
    assert replay.headers["idempotent-replay"] == "true"
    assert detail.status_code == 200
    assert [event["action"] for event in audit.json()] == [
        "workflow.received",
        "workflow.queued",
    ]

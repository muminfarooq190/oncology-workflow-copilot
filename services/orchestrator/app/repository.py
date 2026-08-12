import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db_models import AuditEventRecord, OutboxRecord, WorkflowRecord
from app.domain import WorkflowStatus, ensure_transition, is_normalization_terminal


class WorkflowNotFound(LookupError):
    pass


class IdempotencyConflict(ValueError):
    pass


class WorkflowConflict(ValueError):
    pass


def content_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class WorkflowService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._sessions = session_factory
        self._settings = settings

    async def intake(
        self,
        *,
        bundle: dict[str, Any],
        idempotency_key: str,
        trace_id: str,
        actor_subject: str,
        actor_role: str,
    ) -> tuple[WorkflowRecord, bool]:
        input_hash = content_hash(bundle)
        workflow = WorkflowRecord(
            tenant_id=self._settings.tenant_id,
            idempotency_key=idempotency_key,
            input_hash=input_hash,
            fhir_bundle=bundle,
            status=WorkflowStatus.QUEUED.value,
            max_attempts=self._settings.workflow_max_attempts,
        )

        try:
            async with self._sessions() as session, session.begin():
                session.add(workflow)
                await session.flush()
                self._append_audit(
                    session,
                    workflow,
                    action="workflow.received",
                    prior_state=None,
                    next_state=WorkflowStatus.RECEIVED,
                    trace_id=trace_id,
                    actor_subject=actor_subject,
                    actor_role=actor_role,
                    reason_code="synthetic_bundle_accepted",
                )
                ensure_transition(WorkflowStatus.RECEIVED, WorkflowStatus.QUEUED)
                self._append_audit(
                    session,
                    workflow,
                    action="workflow.queued",
                    prior_state=WorkflowStatus.RECEIVED,
                    next_state=WorkflowStatus.QUEUED,
                    trace_id=trace_id,
                    actor_subject="orchestrator",
                    actor_role="system",
                    reason_code="normalization_requested",
                )
                session.add(self._outbox_record(workflow, trace_id=trace_id))
            return workflow, True
        except IntegrityError:
            existing = await self.get_by_idempotency_key(idempotency_key)
            if existing.input_hash != input_hash:
                raise IdempotencyConflict(
                    "Idempotency-Key was already used with a different FHIR bundle"
                ) from None
            return existing, False

    async def get(self, workflow_id: UUID) -> WorkflowRecord:
        async with self._sessions() as session:
            workflow = await session.get(WorkflowRecord, workflow_id)
            if workflow is None or workflow.tenant_id != self._settings.tenant_id:
                raise WorkflowNotFound(str(workflow_id))
            return workflow

    async def get_by_idempotency_key(self, idempotency_key: str) -> WorkflowRecord:
        async with self._sessions() as session:
            workflow = await session.scalar(
                select(WorkflowRecord).where(
                    WorkflowRecord.tenant_id == self._settings.tenant_id,
                    WorkflowRecord.idempotency_key == idempotency_key,
                )
            )
            if workflow is None:
                raise WorkflowNotFound(idempotency_key)
            return workflow

    async def audit_events(self, workflow_id: UUID) -> list[AuditEventRecord]:
        await self.get(workflow_id)
        async with self._sessions() as session:
            events = await session.scalars(
                select(AuditEventRecord)
                .where(AuditEventRecord.workflow_id == workflow_id)
                .order_by(AuditEventRecord.sequence_id)
            )
            return list(events)

    async def claim_normalization(
        self, workflow_id: UUID, *, outbox_id: UUID, trace_id: str
    ) -> WorkflowRecord | None:
        async with self._sessions() as session, session.begin():
            workflow = await session.scalar(
                select(WorkflowRecord).where(WorkflowRecord.id == workflow_id).with_for_update()
            )
            if workflow is None or workflow.tenant_id != self._settings.tenant_id:
                raise WorkflowNotFound(str(workflow_id))

            current = WorkflowStatus(workflow.status)
            if is_normalization_terminal(current) or current == WorkflowStatus.DEAD_LETTER:
                return None
            if current == WorkflowStatus.VALIDATING:
                return workflow if workflow.active_outbox_id == outbox_id else None
            if current not in {WorkflowStatus.QUEUED, WorkflowStatus.RETRY_WAIT}:
                raise WorkflowConflict(f"Workflow is not ready for normalization: {current}")

            ensure_transition(current, WorkflowStatus.VALIDATING)
            workflow.status = WorkflowStatus.VALIDATING.value
            workflow.active_outbox_id = outbox_id
            workflow.attempts += 1
            workflow.version += 1
            workflow.updated_at = datetime.now(UTC)
            self._append_audit(
                session,
                workflow,
                action="normalization.started",
                prior_state=current,
                next_state=WorkflowStatus.VALIDATING,
                trace_id=trace_id,
                actor_subject="normalization-worker",
                actor_role="system",
                reason_code=f"attempt_{workflow.attempts}",
            )
            return workflow

    async def complete_normalization(
        self,
        workflow_id: UUID,
        *,
        validation_result: dict[str, Any],
        canonical_case: dict[str, Any] | None,
        trace_id: str,
    ) -> WorkflowRecord:
        target = (
            WorkflowStatus.NORMALIZED
            if bool(validation_result.get("isValid")) and canonical_case is not None
            else WorkflowStatus.INVALID
        )
        output = {"validation": validation_result, "canonicalCase": canonical_case}

        async with self._sessions() as session, session.begin():
            workflow = await self._locked_workflow(session, workflow_id)
            current = WorkflowStatus(workflow.status)
            if is_normalization_terminal(current):
                return workflow
            ensure_transition(current, target)
            workflow.status = target.value
            workflow.active_outbox_id = None
            workflow.validation_result = validation_result
            workflow.canonical_case = canonical_case
            workflow.last_error_code = None
            workflow.last_error_message = None
            workflow.version += 1
            workflow.updated_at = datetime.now(UTC)
            self._append_audit(
                session,
                workflow,
                action=f"normalization.{target.value}",
                prior_state=current,
                next_state=target,
                trace_id=trace_id,
                actor_subject="normalization-worker",
                actor_role="system",
                output_hash=content_hash(output),
                reason_code=(
                    "fhir_valid" if target == WorkflowStatus.NORMALIZED else "fhir_invalid"
                ),
            )
            return workflow

    async def fail_normalization(
        self,
        workflow_id: UUID,
        *,
        error_code: str,
        error_message: str,
        trace_id: str,
    ) -> WorkflowRecord:
        async with self._sessions() as session, session.begin():
            workflow = await self._locked_workflow(session, workflow_id)
            current = WorkflowStatus(workflow.status)
            if is_normalization_terminal(current) or current == WorkflowStatus.DEAD_LETTER:
                return workflow
            if current != WorkflowStatus.VALIDATING:
                raise WorkflowConflict(f"Cannot fail normalization from {current}")

            target = (
                WorkflowStatus.RETRY_WAIT
                if workflow.attempts < workflow.max_attempts
                else WorkflowStatus.DEAD_LETTER
            )
            ensure_transition(current, target)
            workflow.status = target.value
            workflow.active_outbox_id = None
            workflow.last_error_code = error_code[:128]
            workflow.last_error_message = error_message
            workflow.version += 1
            workflow.updated_at = datetime.now(UTC)
            self._append_audit(
                session,
                workflow,
                action=f"normalization.{target.value}",
                prior_state=current,
                next_state=target,
                trace_id=trace_id,
                actor_subject="normalization-worker",
                actor_role="system",
                reason_code=error_code,
            )
            if target == WorkflowStatus.RETRY_WAIT:
                available_at = datetime.now(UTC) + timedelta(
                    seconds=self._settings.workflow_retry_delay_seconds
                    * (2 ** (workflow.attempts - 1))
                )
                session.add(
                    self._outbox_record(
                        workflow,
                        trace_id=trace_id,
                        available_at=available_at,
                    )
                )
            return workflow

    async def retry_dead_letter(
        self,
        workflow_id: UUID,
        *,
        trace_id: str,
        actor_subject: str,
        actor_role: str,
    ) -> WorkflowRecord:
        async with self._sessions() as session, session.begin():
            workflow = await self._locked_workflow(session, workflow_id)
            current = WorkflowStatus(workflow.status)
            if current != WorkflowStatus.DEAD_LETTER:
                raise WorkflowConflict("Only a dead-letter workflow can be retried manually")
            ensure_transition(current, WorkflowStatus.QUEUED)
            workflow.status = WorkflowStatus.QUEUED.value
            workflow.active_outbox_id = None
            workflow.attempts = 0
            workflow.last_error_code = None
            workflow.last_error_message = None
            workflow.version += 1
            workflow.updated_at = datetime.now(UTC)
            self._append_audit(
                session,
                workflow,
                action="workflow.manual_retry",
                prior_state=current,
                next_state=WorkflowStatus.QUEUED,
                trace_id=trace_id,
                actor_subject=actor_subject,
                actor_role=actor_role,
                reason_code="manual_retry",
            )
            session.add(self._outbox_record(workflow, trace_id=trace_id))
            return workflow

    async def _locked_workflow(
        self, session: AsyncSession, workflow_id: UUID
    ) -> WorkflowRecord:
        workflow = await session.scalar(
            select(WorkflowRecord).where(WorkflowRecord.id == workflow_id).with_for_update()
        )
        if workflow is None or workflow.tenant_id != self._settings.tenant_id:
            raise WorkflowNotFound(str(workflow_id))
        return workflow

    def _append_audit(
        self,
        session: AsyncSession,
        workflow: WorkflowRecord,
        *,
        action: str,
        prior_state: WorkflowStatus | None,
        next_state: WorkflowStatus,
        trace_id: str,
        actor_subject: str,
        actor_role: str,
        reason_code: str | None,
        output_hash: str | None = None,
    ) -> None:
        session.add(
            AuditEventRecord(
                workflow_id=workflow.id,
                tenant_id=workflow.tenant_id,
                actor_subject=actor_subject,
                actor_role=actor_role,
                action=action,
                trace_id=trace_id,
                prior_state=prior_state.value if prior_state else None,
                next_state=next_state.value,
                input_hash=workflow.input_hash,
                output_hash=output_hash,
                event_metadata={
                    "contractVersion": "1.0.0",
                    "corpusVersion": self._settings.evidence_corpus_version,
                    "modelSnapshot": None,
                    "promptVersion": None,
                    "reasonCode": reason_code,
                },
            )
        )

    @staticmethod
    def _outbox_record(
        workflow: WorkflowRecord,
        *,
        trace_id: str,
        available_at: datetime | None = None,
    ) -> OutboxRecord:
        outbox_id = uuid4()
        return OutboxRecord(
            id=outbox_id,
            workflow_id=workflow.id,
            event_type="workflow.normalization.requested",
            payload={
                "outboxId": str(outbox_id),
                "workflowId": str(workflow.id),
                "tenantId": workflow.tenant_id,
                "traceId": trace_id,
            },
            available_at=available_at or datetime.now(UTC),
        )

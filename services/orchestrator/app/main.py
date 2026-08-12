import asyncio
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Response, status

from app.config import get_settings
from app.db import dispose_engine, get_session_factory, probe_database
from app.db_models import AuditEventRecord, WorkflowRecord
from app.domain import WorkflowStatus
from app.models import (
    AuditActor,
    AuditEventView,
    DependencyHealth,
    HealthResponse,
    WorkflowAccepted,
    WorkflowCreate,
    WorkflowView,
)
from app.redis_client import close_redis, probe_redis
from app.repository import (
    IdempotencyConflict,
    WorkflowConflict,
    WorkflowNotFound,
    WorkflowService,
)

APP_VERSION = "0.3.0"
CONTRACT_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_redis()
    await dispose_engine()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    description=(
        "Synthetic-data-only orchestration API. Draft clinical outputs require authorized "
        "clinician review."
    ),
    lifespan=lifespan,
)


def _service() -> WorkflowService:
    return WorkflowService(get_session_factory(), get_settings())


def _is_synthetic_bundle(bundle: dict[str, Any]) -> bool:
    tags = bundle.get("meta", {}).get("tag", [])
    return any(
        tag.get("system") == "https://oncology-copilot.dev/tags"
        and tag.get("code") == "synthetic"
        for tag in tags
        if isinstance(tag, dict)
    )


def _trace_id(value: str | None) -> str:
    return value or uuid4().hex


def _workflow_view(record: WorkflowRecord) -> WorkflowView:
    return WorkflowView.model_validate(record)


def _audit_view(record: AuditEventRecord) -> AuditEventView:
    return AuditEventView(
        eventId=record.event_id,
        occurredAt=record.occurred_at,
        workflowId=record.workflow_id,
        tenantId=record.tenant_id,
        actor=AuditActor(subject=record.actor_subject, role=record.actor_role),
        action=record.action,
        traceId=record.trace_id,
        priorState=record.prior_state,
        nextState=record.next_state,
        inputHash=record.input_hash,
        outputHash=record.output_hash,
        metadata=record.event_metadata,
    )


async def _probe_fhir() -> None:
    async with httpx.AsyncClient(
        base_url=settings.fhir_integration_url, timeout=3.0
    ) as client:
        response = await client.get("/health")
        response.raise_for_status()


@app.get(
    "/health/live",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    tags=["health"],
)
def liveness() -> HealthResponse:
    return HealthResponse(status="ok", service="orchestrator", version=APP_VERSION)


@app.get(
    "/health/ready",
    response_model=HealthResponse,
    response_model_by_alias=True,
    tags=["health"],
)
async def readiness(response: Response) -> HealthResponse:
    results = await asyncio.gather(
        probe_database(), probe_redis(), _probe_fhir(), return_exceptions=True
    )
    names = ("postgres", "redis", "fhirIntegration")
    dependencies = {
        name: "ok" if not isinstance(result, Exception) else "unavailable"
        for name, result in zip(names, results, strict=True)
    }
    ready = all(value == "ok" for value in dependencies.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if ready else "degraded",
        service="orchestrator",
        version=APP_VERSION,
        dependencies=DependencyHealth(**dependencies),
    )


@app.post(
    "/v1/workflows",
    response_model=WorkflowAccepted,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workflows"],
)
async def create_workflow(
    request: WorkflowCreate,
    response: Response,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    trace_header: str | None = Header(default=None, max_length=128, alias="X-Trace-Id"),
) -> WorkflowAccepted:
    bundle = request.fhir_bundle
    if bundle.get("resourceType") != "Bundle":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="fhirBundle.resourceType must be Bundle",
        )
    if not _is_synthetic_bundle(bundle):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only bundles explicitly tagged as synthetic are accepted",
        )

    try:
        workflow, created = await _service().intake(
            bundle=bundle,
            idempotency_key=idempotency_key,
            trace_id=_trace_id(trace_header),
            actor_subject="orchestrator-api",
            actor_role="system",
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    response.headers["Location"] = f"/v1/workflows/{workflow.id}"
    response.headers["Idempotent-Replay"] = "false" if created else "true"
    return WorkflowAccepted(
        workflowId=workflow.id,
        status=WorkflowStatus(workflow.status),
        receivedAt=workflow.created_at,
        contractVersion=CONTRACT_VERSION,
        message="Workflow queued for durable FHIR validation and normalization.",
    )


@app.get(
    "/v1/workflows/{workflow_id}",
    response_model=WorkflowView,
    response_model_by_alias=True,
    tags=["workflows"],
)
async def get_workflow(workflow_id: UUID) -> WorkflowView:
    try:
        return _workflow_view(await _service().get(workflow_id))
    except WorkflowNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        ) from exc


@app.get(
    "/v1/workflows/{workflow_id}/audit",
    response_model=list[AuditEventView],
    response_model_by_alias=True,
    tags=["workflows"],
)
async def get_workflow_audit(workflow_id: UUID) -> list[AuditEventView]:
    try:
        return [_audit_view(event) for event in await _service().audit_events(workflow_id)]
    except WorkflowNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        ) from exc


@app.post(
    "/v1/workflows/{workflow_id}/retry",
    response_model=WorkflowView,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workflows"],
)
async def retry_workflow(
    workflow_id: UUID,
    trace_header: str | None = Header(default=None, max_length=128, alias="X-Trace-Id"),
) -> WorkflowView:
    try:
        workflow = await _service().retry_dead_letter(
            workflow_id,
            trace_id=_trace_id(trace_header),
            actor_subject="orchestrator-api",
            actor_role="system",
        )
        return _workflow_view(workflow)
    except WorkflowNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        ) from exc
    except WorkflowConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

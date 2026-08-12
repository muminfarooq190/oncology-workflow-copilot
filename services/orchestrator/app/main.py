from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import FastAPI, Header, HTTPException, Response, status

from app.config import get_settings
from app.models import HealthResponse, WorkflowAccepted, WorkflowCreate, WorkflowStatus

APP_VERSION = "0.1.0"
CONTRACT_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Week 7 adds durable dependency probes and connection lifecycle management.
    yield


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


def _is_synthetic_bundle(bundle: dict[str, Any]) -> bool:
    tags = bundle.get("meta", {}).get("tag", [])
    return any(
        tag.get("system") == "https://oncology-copilot.dev/tags"
        and tag.get("code") == "synthetic"
        for tag in tags
        if isinstance(tag, dict)
    )


@app.get("/health/live", response_model=HealthResponse, tags=["health"])
def liveness() -> HealthResponse:
    return HealthResponse(status="ok", service="orchestrator", version=APP_VERSION)


@app.get("/health/ready", response_model=HealthResponse, tags=["health"])
def readiness() -> HealthResponse:
    # Foundation readiness only. Week 7 will verify PostgreSQL, Redis, and FHIR dependencies.
    return HealthResponse(status="ok", service="orchestrator", version=APP_VERSION)


@app.post(
    "/v1/workflows",
    response_model=WorkflowAccepted,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workflows"],
)
def create_workflow(
    request: WorkflowCreate,
    response: Response,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
) -> WorkflowAccepted:
    bundle = request.fhir_bundle
    if bundle.get("resourceType") != "Bundle":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="fhirBundle.resourceType must be Bundle",
        )
    if not _is_synthetic_bundle(bundle):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only bundles explicitly tagged as synthetic are accepted",
        )

    workflow_id = uuid5(NAMESPACE_URL, f"oncology-copilot:{idempotency_key}")
    response.headers["Location"] = f"/v1/workflows/{workflow_id}"
    return WorkflowAccepted(
        workflowId=workflow_id,
        status=WorkflowStatus.RECEIVED,
        receivedAt=datetime.now(UTC),
        contractVersion=CONTRACT_VERSION,
        message=(
            "Input accepted by the Week 5 boundary. Durable queueing and normalization are "
            "implemented in Weeks 6–7."
        ),
    )


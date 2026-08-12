from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain import WorkflowStatus


class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fhir_bundle: dict[str, Any] = Field(alias="fhirBundle")


class WorkflowAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: UUID = Field(alias="workflowId")
    status: WorkflowStatus
    received_at: datetime = Field(alias="receivedAt")
    contract_version: str = Field(alias="contractVersion")
    message: str


class WorkflowView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, populate_by_name=True)

    workflow_id: UUID = Field(alias="workflowId", validation_alias="id")
    status: WorkflowStatus
    attempts: int
    max_attempts: int = Field(alias="maxAttempts")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    validation_result: dict[str, Any] | None = Field(alias="validationResult")
    canonical_case: dict[str, Any] | None = Field(alias="canonicalCase")
    last_error_code: str | None = Field(alias="lastErrorCode")
    last_error_message: str | None = Field(alias="lastErrorMessage")


class AuditActor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    role: str


class AuditEventView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(alias="eventId")
    occurred_at: datetime = Field(alias="occurredAt")
    workflow_id: UUID = Field(alias="workflowId")
    tenant_id: str = Field(alias="tenantId")
    actor: AuditActor
    action: str
    trace_id: str = Field(alias="traceId")
    prior_state: WorkflowStatus | None = Field(alias="priorState")
    next_state: WorkflowStatus = Field(alias="nextState")
    input_hash: str = Field(alias="inputHash")
    output_hash: str | None = Field(alias="outputHash")
    metadata: dict[str, Any]


class DependencyHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    postgres: str
    redis: str
    fhir_integration: str = Field(alias="fhirIntegration")


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    version: str
    dependencies: DependencyHealth | None = None


class EvidenceSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=1_000)
    top_k: int = Field(default=5, ge=1, le=20, alias="topK")
    corpus_version: str | None = Field(default=None, alias="corpusVersion")
    tumor_type: str = Field(default="NSCLC", min_length=2, max_length=64, alias="tumorType")


class EvidenceSearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(alias="chunkId")
    source_title: str = Field(alias="sourceTitle")
    source_url: str = Field(alias="sourceUrl")
    publication_date: date = Field(alias="publicationDate")
    locator: str
    content: str
    content_hash: str = Field(alias="contentHash")
    tags: list[str]
    lexical_rank: int | None = Field(alias="lexicalRank")
    vector_rank: int | None = Field(alias="vectorRank")
    rrf_score: float = Field(alias="rrfScore")


class EvidenceSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    corpus_version: str = Field(alias="corpusVersion")
    embedding_provider: str = Field(alias="embeddingProvider")
    results: list[EvidenceSearchHit]

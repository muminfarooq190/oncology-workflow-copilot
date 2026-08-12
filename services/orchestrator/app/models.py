from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkflowStatus(StrEnum):
    RECEIVED = "received"
    INVALID = "invalid"
    NORMALIZED = "normalized"
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    ESCALATED = "escalated"


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


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


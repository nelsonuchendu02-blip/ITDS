from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..models import DiagnosticResultSeverity, DiagnosticResultStatus, DiagnosticRunStatus, DiagnosticCheckType


class DiagnosticRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: UUID
    diagnostic_type: DiagnosticCheckType = DiagnosticCheckType.CONNECTIVITY
    provider: str = Field(default="simulated", min_length=1, max_length=50)


class DiagnosticResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    diagnostic_run_id: UUID
    organization_id: UUID
    device_id: UUID
    check_identifier: str
    check_type: DiagnosticCheckType
    status: DiagnosticResultStatus
    severity: DiagnosticResultSeverity
    observed_value: dict | None
    expected_value: dict | None
    message: str | None
    evidence: str | None
    title: str
    summary: str | None
    recommendation: str | None
    result_metadata: dict | None
    checked_at: datetime
    created_at: datetime
    updated_at: datetime


class DiagnosticRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    device_id: UUID
    incident_id: UUID | None
    diagnostic_type: str
    provider: str
    status: DiagnosticRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class DiagnosticPageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class DiagnosticRunPage(BaseModel):
    items: list[DiagnosticRunRead]
    meta: DiagnosticPageMeta


class DiagnosticResultPage(BaseModel):
    items: list[DiagnosticResultRead]
    meta: DiagnosticPageMeta

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ..models import (
    RootCauseAnalysisStatus, RootCauseFindingConfidence, RootCauseFindingSeverity,
    RootCauseFindingStatus,
)


class RootCauseAnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagnostic_run_id: UUID


class RootCauseFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    analysis_id: UUID
    rule_id: str
    severity: RootCauseFindingSeverity
    title: str
    summary: str
    organization_id: UUID
    device_id: UUID
    diagnostic_result_id: UUID
    category: str
    status: RootCauseFindingStatus
    confidence: RootCauseFindingConfidence
    explanation: str
    evidence: dict
    created_at: datetime
    updated_at: datetime


class RootCauseAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    diagnostic_run_id: UUID
    device_id: UUID
    initiated_by_user_id: UUID | None
    provider: str
    status: RootCauseAnalysisStatus
    completed_at: datetime | None
    cancelled_at: datetime | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class RootCausePageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class RootCauseAnalysisPage(BaseModel):
    items: list[RootCauseAnalysisRead]
    meta: RootCausePageMeta


class RootCauseFindingPage(BaseModel):
    items: list[RootCauseFindingRead]
    meta: RootCausePageMeta

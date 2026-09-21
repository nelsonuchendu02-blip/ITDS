from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ..models import RecommendationPriority, RecommendationStatus


class RecommendationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root_cause_finding_id: UUID


class RecommendationGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: UUID


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    device_id: UUID | None
    incident_id: UUID | None
    diagnostic_result_id: UUID | None
    root_cause_finding_id: UUID | None
    root_cause_analysis_id: UUID | None
    created_by_user_id: UUID | None
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    title: str
    description: str | None
    rationale: str | None
    rule_id: str
    fingerprint: str
    evidence: dict
    category: str
    severity: str
    summary: str
    expected_effect: str
    confidence: str
    remediation_type: str
    requires_human_approval: bool
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    implemented_at: datetime | None
    implementation_notes: str | None
    priority: RecommendationPriority
    status: RecommendationStatus
    created_at: datetime
    updated_at: datetime


class RecommendationPageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class RecommendationPage(BaseModel):
    items: list[RecommendationRead]
    meta: RecommendationPageMeta

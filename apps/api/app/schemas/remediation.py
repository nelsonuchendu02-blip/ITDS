from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..models import RemediationActionStatus, RemediationPlanStatus, RemediationVerificationStatus


class RemediationGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation_id: UUID


class RemediationActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sequence: int
    action_key: str
    parameters: dict
    status: RemediationActionStatus
    result: dict | None


class RemediationVerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    device_id: UUID
    check_key: str
    status: RemediationVerificationStatus
    observed: dict | None
    details: str | None
    verified_at: datetime | None


class RemediationPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    device_id: UUID
    recommendation_id: UUID | None
    root_cause_finding_id: UUID | None
    created_by_user_id: UUID | None
    approved_by_user_id: UUID | None
    title: str
    rationale: str
    plan_hash: str
    dry_run: bool
    status: RemediationPlanStatus
    verification_status: RemediationVerificationStatus
    approved_at: datetime | None
    executed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    actions: list[RemediationActionRead] = Field(default_factory=list)
    verifications: list[RemediationVerificationRead] = Field(default_factory=list)


class RemediationPlanList(BaseModel):
    items: list[RemediationPlanRead]
    total: int

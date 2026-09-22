from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated

from ..models import IncidentPriority, IncidentSeverity, IncidentStatus, EscalationStatus

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Name
    description: str | None = Field(default=None, max_length=10000)
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    priority: IncidentPriority = IncidentPriority.MEDIUM
    device_id: UUID | None = None
    assigned_user_id: UUID | None = None


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: IncidentStatus | None = None
    priority: IncidentPriority | None = None
    severity: IncidentSeverity | None = None
    assigned_user_id: UUID | None = None
    description: str | None = Field(default=None, max_length=10000)


class IncidentAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_user_id: UUID


class IncidentResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution_summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    device_id: UUID | None
    assigned_user_id: UUID | None
    title: str
    description: str | None
    severity: IncidentSeverity
    priority: IncidentPriority
    status: IncidentStatus
    opened_at: datetime
    resolved_at: datetime | None
    created_by_user_id: UUID | None
    resolved_by_user_id: UUID | None
    resolution_summary: str | None
    closed_at: datetime | None
    closed_by_user_id: UUID | None
    last_escalated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IncidentPage(BaseModel):
    items: list[IncidentRead]
    total: int
    page: int
    page_size: int


class EscalationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    escalation_level: int = Field(ge=1, le=100)
    reason: Reason
    assigned_to: Name | None = None


class EscalationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    incident_id: UUID
    escalation_level: int
    reason: str
    status: EscalationStatus
    assigned_to: str | None
    escalated_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

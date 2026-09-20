from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..models import DiscoveryJobStatus, DiscoveryResultStatus, ReconciliationStatus


class DiscoveryJobCreate(BaseModel):
    provider: str = Field(default="simulated", min_length=1, max_length=50)
    target: str = Field(min_length=1, max_length=255)


class DiscoveryPageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class DiscoveryJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    provider: str
    target_type: str
    target_definition: str
    target_count: int
    status: DiscoveryJobStatus
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class DiscoveryJobPage(BaseModel):
    items: list[DiscoveryJobRead]
    meta: DiscoveryPageMeta


class DiscoveryResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    discovery_job_id: UUID
    organization_id: UUID
    target_ip: str
    discovered_hostname: str | None
    discovered_device_type: str | None
    discovered_operating_system: str | None
    provider: str
    status: DiscoveryResultStatus
    reconciliation_status: ReconciliationStatus
    matched_device_id: UUID | None
    discovered_at: datetime
    result_metadata: dict | None


class DiscoveryResultPage(BaseModel):
    items: list[DiscoveryResultRead]
    meta: DiscoveryPageMeta

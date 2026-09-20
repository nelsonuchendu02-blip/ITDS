from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..models import DeviceStatus


class DeviceCreate(BaseModel):
    organization_id: UUID
    hostname: str = Field(min_length=1, max_length=255)
    device_type: str = Field(min_length=1, max_length=100)
    operating_system: str = Field(min_length=1, max_length=200)
    ip_address: str | None = Field(default=None, max_length=45)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    hostname: str
    device_type: str
    operating_system: str
    ip_address: str | None
    status: DeviceStatus
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..models import OrganizationStatus


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime

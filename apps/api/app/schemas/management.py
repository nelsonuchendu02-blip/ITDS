from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..models import OrganizationStatus, UserStatus


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class OrganizationAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime


class UserCreateAdmin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=1024)


class UserUpdateAdmin(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)


class UserAdminRead(BaseModel):
    id: UUID
    organization_id: UUID
    email: str
    display_name: str
    status: UserStatus
    roles: list[str]
    created_at: datetime
    updated_at: datetime


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    description: str | None


class RoleAssignment(BaseModel):
    role_id: UUID


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class UserPage(BaseModel):
    items: list[UserAdminRead]
    meta: PageMeta


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None
    actor_user_id: UUID | None
    event_type: str
    resource_type: str
    resource_id: str | None
    action: str
    result: str
    event_metadata: dict | None
    created_at: datetime


class AuditEventPage(BaseModel):
    items: list[AuditEventRead]
    meta: PageMeta

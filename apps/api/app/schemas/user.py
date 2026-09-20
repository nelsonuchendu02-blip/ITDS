from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ..models import UserStatus


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    email: str
    display_name: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class CurrentUserRead(UserRead):
    roles: list[str]
    permissions: list[str]

import ipaddress
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import DeviceStatus

_MAC_ADDRESS = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


class DeviceManagementCreate(BaseModel):
    hostname: str = Field(min_length=1, max_length=255)
    device_type: str = Field(min_length=1, max_length=100)
    operating_system: str = Field(min_length=1, max_length=200)
    ip_address: str | None = Field(default=None, max_length=45)

    @field_validator("hostname", "device_type", "operating_system")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ipaddress.ip_address(value)
            except ValueError as exc:
                raise ValueError("Invalid IP address") from exc
        return value


class DeviceManagementUpdate(BaseModel):
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    device_type: str | None = Field(default=None, min_length=1, max_length=100)
    operating_system: str | None = Field(default=None, min_length=1, max_length=200)
    ip_address: str | None = Field(default=None, max_length=45)

    @field_validator("hostname", "device_type", "operating_system")
    @classmethod
    def reject_blank_values(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ipaddress.ip_address(value)
            except ValueError as exc:
                raise ValueError("Invalid IP address") from exc
        return value


class DeviceManagementRead(BaseModel):
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


class DevicePageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class DevicePage(BaseModel):
    items: list[DeviceManagementRead]
    meta: DevicePageMeta

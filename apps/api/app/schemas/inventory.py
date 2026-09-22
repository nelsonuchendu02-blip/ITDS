import ipaddress
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import AssetType, DeviceCriticality

_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InventoryRead(StrictModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime


class SiteCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=500)


class SiteUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=500)


class SiteRead(InventoryRead):
    name: str
    description: str | None
    address: str | None


class NetworkCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    site_id: UUID | None = None
    description: str | None = Field(default=None, max_length=2000)


class NetworkUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    site_id: UUID | None = None
    description: str | None = Field(default=None, max_length=2000)


class NetworkRead(InventoryRead):
    site_id: UUID | None
    name: str
    description: str | None


class SubnetCreate(StrictModel):
    network_id: UUID | None = None
    cidr: str = Field(min_length=1, max_length=64)
    gateway: str | None = Field(default=None, max_length=45)

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str) -> str:
        try:
            return str(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise ValueError("Invalid network CIDR") from exc

    @field_validator("gateway")
    @classmethod
    def validate_gateway(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ipaddress.ip_address(value)
            except ValueError as exc:
                raise ValueError("Invalid gateway address") from exc
        return value


class SubnetUpdate(StrictModel):
    network_id: UUID | None = None
    cidr: str | None = Field(default=None, min_length=1, max_length=64)
    gateway: str | None = Field(default=None, max_length=45)

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise ValueError("Invalid network CIDR") from exc


class SubnetRead(InventoryRead):
    network_id: UUID | None
    cidr: str
    gateway: str | None


class VLANCreate(StrictModel):
    network_id: UUID | None = None
    vlan_id: int = Field(ge=1, le=4094)
    name: str = Field(min_length=1, max_length=200)


class VLANUpdate(StrictModel):
    network_id: UUID | None = None
    vlan_id: int | None = Field(default=None, ge=1, le=4094)
    name: str | None = Field(default=None, min_length=1, max_length=200)


class VLANRead(InventoryRead):
    network_id: UUID | None
    vlan_id: int
    name: str


class SSIDCreate(StrictModel):
    network_id: UUID | None = None
    ssid: str = Field(min_length=1, max_length=32)
    security: str | None = Field(default=None, max_length=100)


class SSIDUpdate(StrictModel):
    network_id: UUID | None = None
    ssid: str | None = Field(default=None, min_length=1, max_length=32)
    security: str | None = Field(default=None, max_length=100)


class SSIDRead(InventoryRead):
    network_id: UUID | None
    ssid: str
    security: str | None


class AssetCreate(StrictModel):
    hostname: str = Field(min_length=1, max_length=255)
    device_type: str = Field(min_length=1, max_length=100)
    operating_system: str = Field(min_length=1, max_length=200)
    operating_system_version: str | None = Field(default=None, max_length=100)
    asset_type: AssetType | None = None
    criticality: DeviceCriticality | None = None
    ip_address: str | None = Field(default=None, max_length=45)
    ipv6_address: str | None = Field(default=None, max_length=45)
    management_ip: str | None = Field(default=None, max_length=45)
    asset_tag: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=255)
    manufacturer: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200)
    firmware_version: str | None = Field(default=None, max_length=100)
    bios_version: str | None = Field(default=None, max_length=100)
    mac_address: str | None = Field(default=None, max_length=17)
    cpu: str | None = Field(default=None, max_length=200)
    memory: str | None = Field(default=None, max_length=100)
    storage: str | None = Field(default=None, max_length=200)
    discovery_source: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=500)
    purchase_date: datetime | None = None
    warranty_expiration: datetime | None = None
    site_id: UUID | None = None
    network_id: UUID | None = None
    subnet_id: UUID | None = None
    vlan_id: UUID | None = None
    wlan_id: UUID | None = None
    assigned_user_id: UUID | None = None

    @field_validator("ip_address", "ipv6_address", "management_ip")
    @classmethod
    def validate_ip(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ipaddress.ip_address(value)
            except ValueError as exc:
                raise ValueError("Invalid IP address") from exc
        return value

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, value: str | None) -> str | None:
        if value is not None and not _MAC.match(value):
            raise ValueError("Invalid MAC address")
        return value


class AssetUpdate(AssetCreate):
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    device_type: str | None = Field(default=None, min_length=1, max_length=100)
    operating_system: str | None = Field(default=None, min_length=1, max_length=200)


class AssetRead(InventoryRead):
    hostname: str
    device_type: str
    asset_type: AssetType | None
    criticality: DeviceCriticality | None
    operating_system: str
    operating_system_version: str | None
    ip_address: str | None
    ipv6_address: str | None
    management_ip: str | None
    asset_tag: str | None
    serial_number: str | None
    manufacturer: str | None
    model: str | None
    firmware_version: str | None
    bios_version: str | None
    mac_address: str | None
    cpu: str | None
    memory: str | None
    storage: str | None
    discovery_source: str | None
    location: str | None
    purchase_date: datetime | None
    warranty_expiration: datetime | None
    site_id: UUID | None
    network_id: UUID | None
    subnet_id: UUID | None
    vlan_id: UUID | None
    wlan_id: UUID | None
    assigned_user_id: UUID | None

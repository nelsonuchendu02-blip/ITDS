from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import HealthStatus


class MonitoringTargetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: UUID
    enabled: bool = True
    check_interval_seconds: int = Field(default=300, ge=10, le=86400)
    offline_after_seconds: int = Field(default=900, ge=10, le=604800)

    @field_validator("offline_after_seconds")
    @classmethod
    def offline_after_interval(cls, value, info):
        if value < info.data.get("check_interval_seconds", 300):
            raise ValueError("offline_after_seconds must be at least check_interval_seconds")
        return value


class MonitoringTargetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    check_interval_seconds: int | None = Field(default=None, ge=10, le=86400)
    offline_after_seconds: int | None = Field(default=None, ge=10, le=604800)


class MonitoringTargetRead(MonitoringTargetCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    organization_id: UUID
    last_seen_at: datetime | None
    last_status_at: datetime | None
    last_error_code: str | None
    health_status: HealthStatus
    created_at: datetime
    updated_at: datetime


class TelemetryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_at: datetime
    received_at: datetime | None = None
    health_status: HealthStatus
    latency_ms: int | None = Field(default=None, ge=0, le=86400000)
    packet_loss_percent: float | None = Field(default=None, ge=0, le=100)
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    disk_percent: float | None = Field(default=None, ge=0, le=100)
    uptime_seconds: int | None = Field(default=None, ge=0)
    source: str = Field(min_length=1, max_length=100)
    details: dict | None = None

    @field_validator("observed_at", "received_at")
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("details")
    @classmethod
    def controlled_details(cls, value):
        if value is None:
            return value
        dangerous = {"command", "cmd", "shell", "exec", "executable", "script", "argv", "arguments"}
        def inspect(item):
            if isinstance(item, dict):
                for key, nested in item.items():
                    lowered = str(key).lower()
                    if lowered in dangerous or any(token in lowered for token in ("command", "exec", "script", "shell")):
                        raise ValueError("details contains an executable field")
                    inspect(nested)
            elif isinstance(item, list):
                for nested in item:
                    inspect(nested)
            elif not isinstance(item, (str, int, float, bool)) and item is not None:
                raise ValueError("details must contain JSON-safe values")
        inspect(value)
        return value


class TelemetryRead(TelemetryCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    organization_id: UUID
    target_id: UUID
    device_id: UUID
    received_at: datetime
    created_at: datetime
    updated_at: datetime


class MonitoringPageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class MonitoringTargetPage(BaseModel):
    items: list[MonitoringTargetRead]
    meta: MonitoringPageMeta


class TelemetryPage(BaseModel):
    items: list[TelemetryRead]
    meta: MonitoringPageMeta


class MonitoringSummary(BaseModel):
    total_targets: int
    enabled_targets: int
    disabled_targets: int
    healthy: int
    degraded: int
    unhealthy: int
    offline: int
    unknown: int

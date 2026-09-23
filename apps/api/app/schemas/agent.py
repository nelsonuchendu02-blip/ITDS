from datetime import datetime
from uuid import UUID

import math
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import AgentStatus, HealthStatus

_FORBIDDEN_METRIC_TOKENS = ("command", "exec", "shell", "script", "password", "secret", "token")


class EnrollmentTokenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expires_in_seconds: int = Field(default=3600, ge=60, le=604800)
    target_device_id: UUID | None = None


class EnrollmentTokenRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    organization_id: UUID
    token: str
    token_prefix: str
    target_device_id: UUID | None
    expires_at: datetime


class AgentEnroll(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=8, max_length=200)
    device_id: UUID | None = None
    agent_name: str = Field(min_length=1, max_length=200)
    agent_version: str | None = Field(default=None, max_length=100)
    platform: str = Field(default="windows", max_length=100)


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_name: str | None = Field(default=None, min_length=1, max_length=200)


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    organization_id: UUID
    device_id: UUID | None
    agent_name: str
    agent_version: str | None
    platform: str
    status: AgentStatus
    enrolled_at: datetime | None
    last_seen_at: datetime | None
    last_ip_address: str | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime


class AgentEnrollmentResponse(BaseModel):
    agent: AgentRead
    credential: str


class AgentHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_at: datetime
    agent_version: str | None = Field(default=None, max_length=100)
    hostname: str | None = Field(default=None, max_length=255)
    platform: str | None = Field(default=None, max_length=100)
    local_ip: str | None = Field(default=None, max_length=45)
    health_status: HealthStatus = HealthStatus.HEALTHY
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @field_validator("metrics")
    @classmethod
    def safe_metrics(cls, value: dict) -> dict:
        if len(value) > 32:
            raise ValueError("metrics may contain at most 32 fields")
        for key in value:
            lowered = str(key).lower()
            if len(str(key)) > 64 or any(token in lowered for token in _FORBIDDEN_METRIC_TOKENS):
                raise ValueError("metrics contains a forbidden field")
            metric = value[key]
            if isinstance(metric, str) and len(metric) > 256:
                raise ValueError("metric strings are too long")
            if isinstance(metric, (int, float)) and not isinstance(metric, bool):
                if not math.isfinite(float(metric)) or abs(float(metric)) > 1_000_000_000:
                    raise ValueError("metric value is out of bounds")
        return value


class AgentRotateResponse(BaseModel):
    credential: str
    expires_at: datetime | None

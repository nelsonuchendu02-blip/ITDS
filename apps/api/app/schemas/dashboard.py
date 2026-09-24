from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DashboardDeviceOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int


class DashboardMonitoringOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_targets: int
    enabled_targets: int
    disabled_targets: int
    healthy: int
    degraded: int
    unhealthy: int
    offline: int
    unknown: int


class DashboardAgentOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int
    active: int


class DashboardIncidentOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    open: int
    in_progress: int


class DashboardDiscoveryOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int
    running: int
    pending: int
    completed: int
    failed: int


class DashboardRecommendationOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int
    pending: int


class DashboardOverview(BaseModel):
    """Organization-scoped, permission-aware aggregate KPIs.

    Each section is present only when the requesting user holds the
    corresponding module's read permission. Absent sections mean the
    user cannot view that data, not that the underlying count is zero.
    """

    model_config = ConfigDict(extra="forbid")
    generated_at: datetime
    devices: DashboardDeviceOverview | None = None
    monitoring: DashboardMonitoringOverview | None = None
    agents: DashboardAgentOverview | None = None
    incidents: DashboardIncidentOverview | None = None
    discovery: DashboardDiscoveryOverview | None = None
    recommendations: DashboardRecommendationOverview | None = None

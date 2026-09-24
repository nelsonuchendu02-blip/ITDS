"""Read-only, permission-aware aggregation for the operations dashboard.

The dashboard needs organization-wide totals (for example "open incidents")
that the paginated module APIs cannot answer accurately or efficiently from
a single page of results. This service computes each aggregate with a scoped
COUNT query rather than loading full result sets, and only includes a
section when the requesting user holds that module's read permission -
matching the authorization boundary already enforced by the module APIs.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Agent,
    AgentStatus,
    Device,
    DiscoveryJob,
    DiscoveryJobStatus,
    Incident,
    IncidentStatus,
    Recommendation,
    RecommendationStatus,
    User,
)
from .authorization import has_permission
from .monitoring import MonitoringService


class DashboardService:
    def __init__(self, monitoring_service: MonitoringService | None = None):
        self._monitoring_service = monitoring_service or MonitoringService()

    def overview(self, session: Session, user: User) -> dict:
        organization_id = user.organization_id
        overview: dict = {"generated_at": datetime.now(timezone.utc)}

        if has_permission(user, "devices:read"):
            overview["devices"] = self._device_overview(session, organization_id)
        if has_permission(user, "monitoring:read"):
            overview["monitoring"] = self._monitoring_service.summary(session, organization_id)
        if has_permission(user, "agents:read"):
            overview["agents"] = self._agent_overview(session, organization_id)
        if has_permission(user, "incidents:read"):
            overview["incidents"] = self._incident_overview(session, organization_id)
        if has_permission(user, "discovery:read"):
            overview["discovery"] = self._discovery_overview(session, organization_id)
        if has_permission(user, "recommendations:read"):
            overview["recommendations"] = self._recommendation_overview(session, organization_id)
        return overview

    @staticmethod
    def _count(session: Session, model, *conditions) -> int:
        return session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0

    def _device_overview(self, session: Session, organization_id: UUID) -> dict:
        total = self._count(session, Device, Device.organization_id == organization_id)
        return {"total": total}

    def _agent_overview(self, session: Session, organization_id: UUID) -> dict:
        total = self._count(session, Agent, Agent.organization_id == organization_id)
        active = self._count(
            session, Agent, Agent.organization_id == organization_id, Agent.status == AgentStatus.ACTIVE
        )
        return {"total": total, "active": active}

    def _incident_overview(self, session: Session, organization_id: UUID) -> dict:
        open_count = self._count(
            session, Incident, Incident.organization_id == organization_id, Incident.status == IncidentStatus.OPEN
        )
        in_progress = self._count(
            session, Incident, Incident.organization_id == organization_id,
            Incident.status == IncidentStatus.IN_PROGRESS,
        )
        return {"open": open_count, "in_progress": in_progress}

    def _discovery_overview(self, session: Session, organization_id: UUID) -> dict:
        rows = session.execute(
            select(DiscoveryJob.status, func.count())
            .where(DiscoveryJob.organization_id == organization_id)
            .group_by(DiscoveryJob.status)
        ).all()
        counts = {status.value: 0 for status in DiscoveryJobStatus}
        total = 0
        for status, count in rows:
            counts[DiscoveryJobStatus(status).value] = count
            total += count
        return {
            "total": total,
            "running": counts[DiscoveryJobStatus.RUNNING.value],
            "pending": counts[DiscoveryJobStatus.PENDING.value],
            "completed": counts[DiscoveryJobStatus.COMPLETED.value],
            "failed": counts[DiscoveryJobStatus.FAILED.value],
        }

    def _recommendation_overview(self, session: Session, organization_id: UUID) -> dict:
        total = self._count(session, Recommendation, Recommendation.organization_id == organization_id)
        pending = self._count(
            session, Recommendation, Recommendation.organization_id == organization_id,
            Recommendation.status == RecommendationStatus.PENDING,
        )
        return {"total": total, "pending": pending}

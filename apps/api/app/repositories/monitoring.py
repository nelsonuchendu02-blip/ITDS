from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import HealthTelemetry, MonitoringTarget


class MonitoringRepository:
    def targets(self, session, organization_id: UUID, offset: int, limit: int,
                enabled: bool | None = None, health_status=None, device_id: UUID | None = None):
        base = select(MonitoringTarget).where(MonitoringTarget.organization_id == organization_id)
        if enabled is not None:
            base = base.where(MonitoringTarget.enabled == enabled)
        if health_status is not None:
            base = base.where(MonitoringTarget.health_status == health_status)
        if device_id is not None:
            base = base.where(MonitoringTarget.device_id == device_id)
        return list(session.scalars(base.order_by(MonitoringTarget.created_at.desc()).offset(offset).limit(limit))), int(
            session.scalar(select(func.count()).select_from(base.subquery())) or 0)

    def target(self, session, organization_id: UUID, target_id: UUID):
        return session.scalar(select(MonitoringTarget).where(
            MonitoringTarget.id == target_id, MonitoringTarget.organization_id == organization_id))

    def telemetry(self, session, organization_id: UUID, target_id: UUID, offset: int, limit: int):
        base = select(HealthTelemetry).where(
            HealthTelemetry.organization_id == organization_id, HealthTelemetry.target_id == target_id)
        return list(session.scalars(base.order_by(HealthTelemetry.observed_at.desc()).offset(offset).limit(limit))), int(
            session.scalar(select(func.count()).select_from(base.subquery())) or 0)

    def summary(self, session, organization_id: UUID):
        return list(session.scalars(select(MonitoringTarget).where(
            MonitoringTarget.organization_id == organization_id)))

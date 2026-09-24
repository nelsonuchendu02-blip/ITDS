from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import PersistenceError, SecurityError
from ..models import Device, HealthStatus, HealthTelemetry, MonitoringTarget, User
from ..repositories.monitoring import MonitoringRepository
from .audit import record_security_event


class MonitoringService:
    def __init__(self, repository=None):
        self.repository = repository or MonitoringRepository()

    def create_target(self, session: Session, actor: User, values: dict):
        if session.scalar(select(Device.id).where(Device.id == values["device_id"],
                                                  Device.organization_id == actor.organization_id)) is None:
            raise SecurityError("device_not_found", "Device not found", 404)
        interval = values.get("check_interval_seconds", 300)
        offline_after = values.get("offline_after_seconds", 900)
        if offline_after < interval:
            raise SecurityError("invalid_interval", "Offline threshold must be at least the check interval", 422)
        target = MonitoringTarget(organization_id=actor.organization_id, **values)
        session.add(target)
        record_security_event(session, event_type="monitoring_target_created", organization_id=actor.organization_id,
                              actor_user_id=actor.id, action="create", result="success",
                              resource_type="monitoring_target", resource_id=str(target.id))
        return self._commit(session, target, "created")

    def update_target(self, session, target, actor, values: dict):
        self._scope(target, actor)
        interval = values.get("check_interval_seconds", target.check_interval_seconds)
        offline_after = values.get("offline_after_seconds", target.offline_after_seconds)
        if offline_after < interval:
            raise SecurityError("invalid_interval", "Offline threshold must be at least the check interval", 422)
        for key, value in values.items():
            setattr(target, key, value)
        record_security_event(session, event_type="monitoring_target_updated",
                              organization_id=actor.organization_id, actor_user_id=actor.id,
                              action="update", result="success", resource_type="monitoring_target",
                              resource_id=str(target.id))
        return self._commit(session, target, "updated")

    def set_enabled(self, session, target, actor, enabled: bool):
        self._scope(target, actor)
        target.enabled = enabled
        record_security_event(session, event_type="monitoring_target_enabled" if enabled else "monitoring_target_disabled",
                              organization_id=actor.organization_id, actor_user_id=actor.id, action="update",
                              result="success", resource_type="monitoring_target", resource_id=str(target.id))
        return self._commit(session, target, "updated")

    @staticmethod
    def effective_status(target):
        if not target.enabled:
            return target.health_status
        if target.last_seen_at is None:
            return HealthStatus.UNKNOWN
        seen = target.last_seen_at
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - seen).total_seconds() > target.offline_after_seconds:
            return HealthStatus.OFFLINE
        return target.health_status

    def target_read(self, target):
        return {
            "id": target.id, "organization_id": target.organization_id, "device_id": target.device_id,
            "enabled": target.enabled, "check_interval_seconds": target.check_interval_seconds,
            "offline_after_seconds": target.offline_after_seconds, "last_seen_at": target.last_seen_at,
            "last_status_at": target.last_status_at, "last_error_code": target.last_error_code,
            "health_status": self.effective_status(target),
            "created_at": target.created_at, "updated_at": target.updated_at,
        }

    def target_page(self, session, organization_id, offset, limit, **filters):
        requested_status = filters.pop("health_status", None)
        # Health is effective (including stale -> offline), so filter after mapping.
        items, _ = self.repository.targets(session, organization_id, 0, 100000, **filters)
        mapped = [self.target_read(item) for item in items]
        if requested_status is not None:
            mapped = [item for item in mapped if item["health_status"] == requested_status]
        return mapped[offset:offset + limit], len(mapped)

    def ingest(self, session, target, actor, values: dict):
        self._scope(target, actor)
        return self._apply_ingest(session, target, actor.organization_id, actor.id, values)

    def ingest_for_agent(self, session, target, organization_id, values: dict):
        """Converge agent heartbeat telemetry through the same Phase 1L validation
        and update path used by human-submitted telemetry, attributing the audit
        event to the agent rather than a human actor."""
        if target.organization_id != organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
        return self._apply_ingest(session, target, organization_id, None, values)

    def _apply_ingest(self, session, target, organization_id, actor_user_id, values: dict):
        if not target.enabled:
            raise SecurityError("monitoring_target_disabled", "Monitoring target is disabled", 409)
        now = datetime.now(timezone.utc)
        observed = values["observed_at"]
        received = values.get("received_at") or now
        if observed > now or received > now or received < observed:
            raise SecurityError("invalid_timestamp", "Telemetry timestamps are invalid", 422)
        telemetry_values = dict(values)
        telemetry_values.pop("received_at", None)
        telemetry = HealthTelemetry(organization_id=organization_id, target_id=target.id,
                                    device_id=target.device_id, received_at=received, **telemetry_values)
        previous_status = target.health_status
        previous_seen = target.last_seen_at
        if previous_seen is not None and previous_seen.tzinfo is None:
            previous_seen = previous_seen.replace(tzinfo=timezone.utc)
        if previous_seen is None or observed > previous_seen:
            target.last_seen_at = observed
        if previous_status != values["health_status"]:
            status_at = received
            if target.last_status_at is not None:
                prior_status_at = target.last_status_at
                if prior_status_at.tzinfo is None:
                    prior_status_at = prior_status_at.replace(tzinfo=timezone.utc)
                if status_at <= prior_status_at:
                    from datetime import timedelta
                    status_at = prior_status_at + timedelta(microseconds=1)
            target.last_status_at = status_at
            target.health_status = values["health_status"]
        device = session.scalar(select(Device).where(
            Device.id == target.device_id, Device.organization_id == organization_id))
        device_seen = device.last_seen_at if device is not None else None
        if device_seen is not None and device_seen.tzinfo is None:
            device_seen = device_seen.replace(tzinfo=timezone.utc)
        if device is not None and (device_seen is None or observed > device_seen):
            device.last_seen_at = observed
        details = values.get("details") or {}
        target.last_error_code = details.get("error_code") if isinstance(details, dict) else None
        session.add(telemetry)
        record_security_event(session, event_type="health_telemetry_ingested", organization_id=organization_id,
                              actor_user_id=actor_user_id, action="create", result="success",
                              resource_type="health_telemetry", resource_id=str(telemetry.id))
        return self._commit(session, telemetry, "ingested")

    def summary(self, session, organization_id):
        targets = self.repository.summary(session, organization_id)
        counts = {status.value: 0 for status in HealthStatus}
        for target in targets:
            if not target.enabled:
                continue
            status = self.effective_status(target)
            counts[status.value] += 1
        return {"total_targets": len(targets), "enabled_targets": sum(t.enabled for t in targets),
                "disabled_targets": sum(not t.enabled for t in targets),
                **{key: counts.get(key, 0) for key in ("healthy", "degraded", "unhealthy", "offline", "unknown")}}

    @staticmethod
    def _scope(target, actor):
        if target.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)

    @staticmethod
    def _commit(session, resource, action):
        try:
            session.commit()
            session.refresh(resource)
            return resource
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError(f"Resource could not be {action}") from exc

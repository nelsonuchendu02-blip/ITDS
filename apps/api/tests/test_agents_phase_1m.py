"""Phase 1M contract tests that also run without a live PostgreSQL instance."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import (
    Agent, AgentStatus, AuditEvent, Base, Device, HealthStatus, MonitoringTarget, Organization,
)
from app.schemas.agent import AgentHeartbeat
from app.services.agent import AgentService


def test_agent_status_values_are_exact():
    assert {item.value for item in AgentStatus} == {
        "pending", "active", "offline", "revoked", "retired",
    }


def test_heartbeat_rejects_unbounded_or_sensitive_metrics():
    with pytest.raises(ValueError):
        AgentHeartbeat(
            observed_at=datetime.now(timezone.utc),
            metrics={f"metric_{n}": n for n in range(33)},
        )
    with pytest.raises(ValueError):
        AgentHeartbeat(
            observed_at=datetime.now(timezone.utc),
            metrics={"shell_output": "not allowed"},
        )


def test_heartbeat_accepts_bounded_safe_metrics():
    payload = AgentHeartbeat(
        observed_at=datetime.now(timezone.utc),
        metrics={"cpu_percent": 42.5, "healthy": True},
    )
    assert payload.metrics["cpu_percent"] == 42.5


def test_heartbeat_requires_timezone():
    with pytest.raises(ValueError):
        AgentHeartbeat(observed_at=datetime(2026, 1, 1))


def test_repeated_heartbeats_do_not_create_security_audit_flood():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        organization = Organization(name="Audit test")
        device = Device(
            organization=organization,
            hostname="audit-device",
            device_type="server",
            operating_system="Linux",
        )
        agent = Agent(
            organization=organization,
            device=device,
            agent_name="audit-agent",
            platform="windows",
        )
        session.add_all([organization, device, agent])
        session.flush()
        target = MonitoringTarget(
            organization_id=organization.id,
            device_id=device.id,
            health_status=HealthStatus.UNKNOWN,
        )
        session.add(target)
        session.commit()
        service = AgentService()
        heartbeat = {
            "observed_at": datetime.now(timezone.utc),
            "agent_version": "1.0",
            "health_status": HealthStatus.HEALTHY,
            "metrics": {"cpu_percent": 10},
        }
        service.heartbeat(session, agent, "127.0.0.1", heartbeat)
        service.heartbeat(session, agent, "127.0.0.1", heartbeat)
        assert session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "agent_heartbeat")
        ).all() == []

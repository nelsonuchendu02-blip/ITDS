from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sqlalchemy.exc import IntegrityError
from app.models import Base, Device, HealthStatus, HealthTelemetry, MonitoringTarget, Organization, Role, User
from app.schemas.monitoring import TelemetryCreate
from app.services.monitoring import MonitoringService
from app.main import app
from app.db import get_db
from app.security.tokens import create_access_token
from app.config import get_settings
from alembic import command
from alembic.config import Config


@pytest.fixture
def monitoring_context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        organization = Organization(name="Monitoring org")
        actor = User(organization=organization, email="monitor@test", display_name="Monitor")
        actor.roles.append(Role(organization=organization, name="organization_admin"))
        device = Device(organization=organization, hostname="monitor-device", device_type="server",
                        operating_system="Linux")
        session.add_all([organization, actor, device])
        session.commit()
        yield session, actor, device


@pytest.fixture
def api_context(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "monitoring-test-" + "x" * 32)
    get_settings.cache_clear()
    with factory() as session:
        org = Organization(name="API org")
        admin = User(organization=org, email="api-admin@test", display_name="Admin")
        admin.roles.append(Role(organization=org, name="organization_admin"))
        viewer = User(organization=org, email="api-viewer@test", display_name="Viewer")
        viewer.roles.append(Role(organization=org, name="viewer"))
        device = Device(organization=org, hostname="api-device", device_type="server", operating_system="Linux")
        session.add_all([org, admin, viewer, device])
        session.commit()
        ids = (admin.id, viewer.id, device.id)
    def override():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = override
    yield TestClient(app), ids
    app.dependency_overrides.pop(get_db, None)


def test_api_auth_rbac_lifecycle_and_isolation(api_context):
    client, (admin_id, viewer_id, device_id) = api_context
    admin = {"Authorization": f"Bearer {create_access_token(admin_id)}"}
    viewer = {"Authorization": f"Bearer {create_access_token(viewer_id)}"}
    payload = {"device_id": str(device_id), "check_interval_seconds": 60, "offline_after_seconds": 120}
    assert client.get("/api/v1/monitoring/targets").status_code == 401
    assert client.post("/api/v1/monitoring/targets", json=payload, headers=viewer).status_code == 403
    response = client.post("/api/v1/monitoring/targets", json=payload, headers=admin)
    assert response.status_code == 201
    target_id = response.json()["id"]
    assert client.get(f"/api/v1/monitoring/targets/{target_id}", headers=admin).status_code == 200
    assert client.get(f"/api/v1/monitoring/targets/{target_id}", headers=viewer).status_code == 200
    assert client.patch(f"/api/v1/monitoring/targets/{target_id}",
                        json={"enabled": False}, headers=viewer).status_code == 403
    assert client.post(f"/api/v1/monitoring/targets/{target_id}/enable", headers=viewer).status_code == 403
    assert client.post(
        f"/api/v1/monitoring/targets/{target_id}/telemetry",
        json={"observed_at": "2026-09-22T22:00:00Z", "health_status": "healthy", "source": "agent"},
        headers=viewer,
    ).status_code == 403
    assert client.patch(f"/api/v1/monitoring/targets/{target_id}",
                        json={"offline_after_seconds": 180}, headers=admin).status_code == 200
    assert client.get("/api/v1/monitoring/targets?enabled=true&page_size=1", headers=admin).json()["meta"]["total"] == 1
    assert client.post(f"/api/v1/monitoring/targets/{target_id}/disable", headers=admin).status_code == 200
    assert client.get("/api/v1/monitoring/summary", headers=admin).json()["disabled_targets"] == 1


def test_cross_org_device_and_target_are_not_accessible(monitoring_context):
    session, actor, device = monitoring_context
    other = Organization(name="Other org")
    other_device = Device(organization=other, hostname="other-device", device_type="server", operating_system="Linux")
    other_user = User(organization=other, email="other@test", display_name="Other")
    other_user.roles.append(Role(organization=other, name="organization_admin"))
    session.add_all([other, other_device, other_user])
    session.commit()
    service = MonitoringService()
    with pytest.raises(Exception):
        service.create_target(session, actor, {"device_id": other_device.id})
    with pytest.raises(Exception):
        service.create_target(session, other_user, {"device_id": device.id})


def test_telemetry_schema_rejects_extra_and_naive_timestamps():
    with pytest.raises(ValueError):
        TelemetryCreate(observed_at=datetime.now(), health_status=HealthStatus.HEALTHY, source="agent")
    with pytest.raises(ValueError):
        TelemetryCreate(observed_at=datetime.now(timezone.utc), health_status=HealthStatus.HEALTHY,
                        source="agent", unexpected=True)


def test_ingest_updates_target_fields_and_audits(monitoring_context):
    session, actor, device = monitoring_context
    target = MonitoringTarget(organization_id=actor.organization_id, device_id=device.id,
                              check_interval_seconds=300)
    session.add(target)
    session.commit()
    observed = datetime.now(timezone.utc) - timedelta(seconds=5)
    telemetry = MonitoringService().ingest(
        session, target, actor,
        {"observed_at": observed, "health_status": HealthStatus.HEALTHY,
         "source": "agent", "details": {"error_code": None}, "latency_ms": 12,
         "packet_loss_percent": 1.5, "cpu_percent": 20, "memory_percent": 30,
         "disk_percent": 40, "uptime_seconds": 99},
    )
    assert telemetry.target_id == target.id
    assert target.last_seen_at.replace(tzinfo=timezone.utc) == observed
    assert target.health_status is HealthStatus.HEALTHY
    assert telemetry.latency_ms == 12
    assert telemetry.packet_loss_percent == 1.5
    assert device.last_seen_at is not None


def test_status_timestamp_only_changes_on_transition(monitoring_context):
    session, actor, device = monitoring_context
    target = MonitoringTarget(organization_id=actor.organization_id, device_id=device.id)
    session.add(target)
    session.commit()
    service = MonitoringService()
    first = datetime.now(timezone.utc) - timedelta(seconds=4)
    service.ingest(session, target, actor, {"observed_at": first, "health_status": HealthStatus.HEALTHY, "source": "a"})
    changed_at = target.last_status_at
    second = first + timedelta(seconds=1)
    service.ingest(session, target, actor, {"observed_at": second, "health_status": HealthStatus.HEALTHY, "source": "a"})
    assert target.last_status_at == changed_at
    service.ingest(session, target, actor, {"observed_at": second, "health_status": HealthStatus.DEGRADED, "source": "a"})
    assert target.last_status_at != changed_at


def test_duplicate_target_is_rejected(monitoring_context):
    session, actor, device = monitoring_context
    service = MonitoringService()
    service.create_target(session, actor, {"device_id": device.id})
    with pytest.raises(Exception):
        service.create_target(session, actor, {"device_id": device.id})


def test_executable_details_are_rejected():
    with pytest.raises(ValueError):
        TelemetryCreate(observed_at=datetime.now(timezone.utc), health_status=HealthStatus.HEALTHY,
                        source="agent", details={"command": "whoami"})


def test_summary_marks_stale_enabled_target_offline(monitoring_context):
    session, actor, device = monitoring_context
    session.add(MonitoringTarget(
        organization_id=actor.organization_id, device_id=device.id, check_interval_seconds=10,
        offline_after_seconds=10,
        last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=20),
        health_status=HealthStatus.HEALTHY,
    ))
    session.commit()
    summary = MonitoringService().summary(session, actor.organization_id)
    assert summary["total_targets"] == 1
    assert summary["offline"] == 1


def test_effective_status_and_database_constraints(monitoring_context):
    session, actor, device = monitoring_context
    target = MonitoringTarget(
        organization_id=actor.organization_id, device_id=device.id,
        check_interval_seconds=10, offline_after_seconds=10,
        last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=20),
        health_status=HealthStatus.HEALTHY,
    )
    session.add(target)
    session.commit()
    assert MonitoringService().target_read(target)["health_status"] is HealthStatus.OFFLINE
    indexes = {item["name"] for item in inspect(session.bind).get_indexes("health_telemetry")}
    assert "ix_health_telemetry_org_device_observed" in indexes
    constraints = inspect(session.bind).get_unique_constraints("monitoring_targets")
    assert any(c["name"] == "uq_monitoring_targets_org_device" for c in constraints)


def test_target_page_filters_effective_offline_status(monitoring_context):
    session, actor, device = monitoring_context
    target = MonitoringTarget(
        organization_id=actor.organization_id, device_id=device.id,
        check_interval_seconds=10, offline_after_seconds=10,
        last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=30),
        health_status=HealthStatus.HEALTHY,
    )
    session.add(target)
    session.commit()
    items, total = MonitoringService().target_page(
        session, actor.organization_id, 0, 10, health_status=HealthStatus.OFFLINE)
    assert total == 1
    assert items[0]["health_status"] is HealthStatus.OFFLINE


def test_invalid_timestamp_and_metric_bounds_are_rejected(monitoring_context):
    session, actor, device = monitoring_context
    target = MonitoringTarget(organization_id=actor.organization_id, device_id=device.id)
    session.add(target)
    session.commit()
    service = MonitoringService()
    future = datetime.now(timezone.utc) + timedelta(minutes=1)
    with pytest.raises(Exception):
        service.ingest(session, target, actor, {
            "observed_at": future, "health_status": HealthStatus.HEALTHY, "source": "agent"})
    with pytest.raises(ValueError):
        TelemetryCreate(observed_at=datetime.now(timezone.utc), health_status=HealthStatus.HEALTHY,
                        source="agent", cpu_percent=101)


def test_fresh_sqlite_migration_lifecycle(monkeypatch):
    database = Path("phase1l_test_lifecycle.db")
    if database.exists():
        database.unlink()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "a7b8c9d0e1f2")
    assert database.exists()
    database.unlink()

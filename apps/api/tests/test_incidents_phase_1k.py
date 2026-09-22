from datetime import datetime, timezone
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.config import get_settings
from app.db import get_db
from app.security.tokens import create_access_token
from app.models import AuditEvent, Base, Device, EscalationStatus, Incident, IncidentStatus, Organization, Role, User
from app.exceptions import SecurityError
from app.schemas import IncidentCreate
from app.services.incident import IncidentService
from app.permissions import permissions_for_roles


@dataclass
class HttpContext:
    session_factory: object
    admin_token: str
    technician_token: str
    other_token: str
    device_id: str
    other_device_id: str


@pytest.fixture
def http_context(monkeypatch: pytest.MonkeyPatch) -> Iterator[HttpContext]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import sessionmaker
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "phase1k-http-" + "x" * 32)
    get_settings.cache_clear()
    with session_factory() as session:
        org = Organization(name="HTTP org")
        other_org = Organization(name="Other HTTP org")
        admin = User(organization=org, email="http-admin@test", display_name="Admin")
        admin.roles.append(Role(organization=org, name="organization_admin"))
        technician = User(organization=org, email="http-tech@test", display_name="Tech")
        technician.roles.append(Role(organization=org, name="technician"))
        other = User(organization=other_org, email="other@test", display_name="Other")
        other.roles.append(Role(organization=other_org, name="organization_admin"))
        device = Device(organization=org, hostname="http-device", device_type="server", operating_system="Linux")
        other_device = Device(organization=other_org, hostname="other-device", device_type="server", operating_system="Linux")
        session.add_all([org, other_org, admin, technician, other, device, other_device])
        session.commit()
        context = HttpContext(
            session_factory, create_access_token(admin.id), create_access_token(technician.id),
            create_access_token(other.id), str(device.id), str(other_device.id),
        )
    def override_get_db():
        with session_factory() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield context
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.fixture
def incident_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    org = Organization(name="Phase 1K")
    actor = User(organization=org, email="actor@phase1k.test", display_name="Actor")
    assignee = User(organization=org, email="assignee@phase1k.test", display_name="Assignee")
    device = Device(organization=org, hostname="phase1k-device", device_type="server", operating_system="Linux")
    session.add_all([org, actor, assignee, device])
    session.commit()
    yield session, actor, assignee, device
    session.close()


def test_incident_explicit_lifecycle_and_audit(incident_db):
    session, actor, assignee, device = incident_db
    service = IncidentService()
    incident = service.create(session, actor=actor, title="Outage", device_id=device.id)
    service.assign(session, incident, actor=actor, assigned_user_id=assignee.id)
    service.start(session, incident, actor=actor)
    with pytest.raises(Exception):
        service.close(session, incident, actor=actor)
    service.resolve(session, incident, actor=actor, resolution_summary="Restored service")
    service.close(session, incident, actor=actor)
    assert incident.status is IncidentStatus.CLOSED
    assert incident.resolved_by_user_id == actor.id
    assert incident.closed_by_user_id == actor.id
    assert incident.closed_at is not None
    assert {event.event_type for event in session.scalars(select(AuditEvent))} >= {
        "incident_started", "incident_resolved", "incident_closed", "incident_assigned",
    }


def test_escalation_lifecycle_and_duplicate_level_constraint(incident_db):
    session, actor, _assignee, _device = incident_db
    service = IncidentService()
    incident = service.create(session, actor=actor, title="Alert")
    escalation = service.escalate(session, incident, actor=actor, escalation_level=1, reason="SLA")
    with pytest.raises(SecurityError):
        service.escalate(session, incident, actor=actor, escalation_level=1, reason="Duplicate")
    service.transition_escalation(session, escalation, actor=actor, target=EscalationStatus.ACKNOWLEDGED)
    assert escalation.status.value == "acknowledged"
    assert {event.event_type for event in session.scalars(select(AuditEvent))} >= {
        "escalation_created", "escalation_acknowledged",
    }


def test_escalation_cannot_skip_acknowledgement(incident_db):
    session, actor, _assignee, _device = incident_db
    service = IncidentService()
    incident = service.create(session, actor=actor, title="Alert")
    escalation = service.escalate(session, incident, actor=actor, escalation_level=1, reason="SLA")
    with pytest.raises(SecurityError, match="Invalid escalation lifecycle"):
        service.transition_escalation(
            session, escalation, actor=actor, target=EscalationStatus.RESOLVED
        )


def test_escalation_lifecycle_is_strict_and_terminal(incident_db):
    session, actor, _assignee, _device = incident_db
    service = IncidentService()
    incident = service.create(session, actor=actor, title="Alert")
    escalation = service.escalate(session, incident, actor=actor, escalation_level=1, reason="SLA")
    with pytest.raises(SecurityError, match="Invalid escalation lifecycle"):
        service.transition_escalation(
            session, escalation, actor=actor, target=EscalationStatus.OPEN
        )
    service.transition_escalation(
        session, escalation, actor=actor, target=EscalationStatus.ACKNOWLEDGED
    )
    service.transition_escalation(
        session, escalation, actor=actor, target=EscalationStatus.RESOLVED
    )
    with pytest.raises(SecurityError, match="Invalid escalation lifecycle"):
        service.transition_escalation(
            session, escalation, actor=actor, target=EscalationStatus.ACKNOWLEDGED
        )


def test_lifecycle_mutations_reject_cross_organization_actor(incident_db):
    session, actor, _assignee, _device = incident_db
    other_org = Organization(name="Other actor org")
    other_actor = User(
        organization=other_org, email="other@phase1k.test", display_name="Other"
    )
    session.add_all([other_org, other_actor])
    session.commit()
    service = IncidentService()
    incident = service.create(session, actor=actor, title="Scoped")
    escalation = service.escalate(session, incident, actor=actor, escalation_level=1, reason="SLA")
    for operation in (
        lambda: service.start(session, incident, actor=other_actor),
        lambda: service.assign(session, incident, actor=other_actor, assigned_user_id=actor.id),
        lambda: service.transition_escalation(
            session, escalation, actor=other_actor, target=EscalationStatus.ACKNOWLEDGED
        ),
    ):
        with pytest.raises(SecurityError, match="not found"):
            operation()


def test_phase_1k_permissions_are_deliberately_scoped():
    admin = permissions_for_roles(["organization_admin"])
    technician = permissions_for_roles(["technician"])
    support = permissions_for_roles(["it_support"])
    assert {"incidents:assign", "incidents:resolve", "incidents:close",
            "escalations:resolve"} <= admin
    assert "incidents:assign" in technician
    assert "incidents:resolve" not in technician
    assert "incidents:close" not in technician
    assert "escalations:resolve" not in support


def test_phase_1k_cross_organization_device_reference_is_rejected(incident_db):
    session, actor, _assignee, _device = incident_db
    other_org = Organization(name="Other")
    other_device = Device(
        organization=other_org, hostname="other-device",
        device_type="server", operating_system="Linux",
    )
    session.add_all([other_org, other_device])
    session.commit()
    service = IncidentService()
    with pytest.raises(SecurityError, match="not in this organization"):
        service.create(session, actor=actor, title="Cross-org", device_id=other_device.id)
    session.rollback()

    session.connection().exec_driver_sql("PRAGMA foreign_keys=ON")
    with pytest.raises(IntegrityError):
        session.execute(Incident.__table__.insert().values(
            organization_id=actor.organization_id,
            device_id=other_device.id,
            title="DB cross-org",
            opened_at=datetime.now(timezone.utc),
        ))
        session.flush()
    session.rollback()


def test_phase_1k_http_routes_and_strict_schema():
    paths = {route.path for route in app.routes}
    assert {
        "/api/v1/incidents/{incident_id}/start",
        "/api/v1/incidents/{incident_id}/resolve",
        "/api/v1/incidents/{incident_id}/close",
        "/api/v1/incidents/{incident_id}/assign",
        "/api/v1/incidents/{incident_id}/escalations/{escalation_id}/resolve",
    } <= paths
    with pytest.raises(ValueError):
        IncidentCreate(title="x", unexpected="rejected")
    response = TestClient(app).post("/api/v1/incidents", json={"title": "x"})
    assert response.status_code in (401, 503)


def test_phase_1k_http_permissions_isolation_input_and_audit(http_context: HttpContext):
    client = TestClient(app)
    admin = {"Authorization": f"Bearer {http_context.admin_token}"}
    technician = {"Authorization": f"Bearer {http_context.technician_token}"}
    other = {"Authorization": f"Bearer {http_context.other_token}"}

    denied = client.post(
        "/api/v1/incidents", headers=technician,
        json={"title": "Injected", "device_id": http_context.device_id, "unexpected": "reject"},
    )
    assert denied.status_code == 422
    created = client.post(
        "/api/v1/incidents", headers=technician,
        json={"title": "HTTP incident", "device_id": http_context.device_id},
    )
    assert created.status_code == 201
    incident_id = created.json()["id"]
    assert client.post(f"/api/v1/incidents/{incident_id}/start", headers=technician).status_code == 403
    assert client.post(f"/api/v1/incidents/{incident_id}/start", headers=admin).status_code == 200
    assert client.post(
        f"/api/v1/incidents/{incident_id}/resolve", headers=technician,
        json={"resolution_summary": "fixed"},
    ).status_code == 403
    assert client.post(
        f"/api/v1/incidents/{incident_id}/resolve", headers=admin,
        json={"resolution_summary": "fixed", "status": "closed"},
    ).status_code == 422
    assert client.post(
        f"/api/v1/incidents/{incident_id}/resolve", headers=admin,
        json={"resolution_summary": "fixed"},
    ).status_code == 200
    assert client.post(f"/api/v1/incidents/{incident_id}/close", headers=admin).status_code == 200
    assert client.get(f"/api/v1/incidents/{incident_id}", headers=other).status_code == 404

    with http_context.session_factory() as session:
        events = session.scalars(select(AuditEvent)).all()
        assert {event.event_type for event in events} >= {
            "incident_created", "incident_started", "incident_resolved", "incident_closed",
        }


def test_phase_1k_http_cross_org_device_and_escalation_lifecycle(http_context: HttpContext):
    client = TestClient(app)
    admin = {"Authorization": f"Bearer {http_context.admin_token}"}
    other = {"Authorization": f"Bearer {http_context.other_token}"}
    created = client.post(
        "/api/v1/incidents", headers=admin,
        json={"title": "Cross-org device", "device_id": http_context.other_device_id},
    )
    assert created.status_code == 422
    incident = client.post("/api/v1/incidents", headers=admin, json={"title": "Escalation"}).json()
    incident_id = incident["id"]
    escalation = client.post(
        f"/api/v1/incidents/{incident_id}/escalations", headers=admin,
        json={"escalation_level": 1, "reason": "SLA"},
    )
    assert escalation.status_code == 201
    escalation_id = escalation.json()["id"]
    assert client.post(
        f"/api/v1/incidents/{incident_id}/escalations/{escalation_id}/resolve",
        headers=admin,
    ).status_code == 409
    assert client.post(
        f"/api/v1/incidents/{incident_id}/escalations/{escalation_id}/acknowledge",
        headers=admin,
    ).status_code == 200
    assert client.post(
        f"/api/v1/incidents/{incident_id}/escalations/{escalation_id}/resolve",
        headers=other,
    ).status_code == 404
    assert client.post(
        f"/api/v1/incidents/{incident_id}/escalations/{escalation_id}/resolve",
        headers=admin,
    ).status_code == 200


def test_phase_1k_migration_schema_and_lifecycle(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'phase1k.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        columns = {column["name"] for column in inspect(engine).get_columns("incidents")}
        assert {
            "created_by_user_id", "resolved_by_user_id", "closed_by_user_id",
            "closed_at", "resolution_summary", "last_escalated_at",
        } <= columns
        incident_fks = {
            fk["name"]: (tuple(fk["constrained_columns"]), tuple(fk["referred_columns"]))
            for fk in inspect(engine).get_foreign_keys("incidents")
        }
        assert incident_fks["fk_incidents_created_by_user_org"] == (
            ("created_by_user_id", "organization_id"), ("id", "organization_id")
        )
        command.downgrade(config, "d4f6a1b2c3e4")
        command.upgrade(config, "head")
        assert "uq_escalations_incident_level" in {
            constraint["name"] for constraint in inspect(engine).get_unique_constraints("escalations")
        }
    finally:
        engine.dispose()
        get_settings.cache_clear()

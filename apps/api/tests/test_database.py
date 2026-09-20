import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.exceptions import PersistenceError
from app.exceptions import SecurityError
from app.models import (
    Base,
    AuditEvent,
    Device,
    DeviceStatus,
    DiagnosticRun,
    DiagnosticRunStatus,
    Escalation,
    EscalationStatus,
    Incident,
    IncidentPriority,
    IncidentSeverity,
    IncidentStatus,
    Organization,
    Recommendation,
    RecommendationPriority,
    RecommendationStatus,
    RepairAction,
    RepairActionStatus,
    Role,
    User,
    UserStatus,
)
from app.schemas import DeviceCreate, DeviceManagementCreate, OrganizationCreate
from app.services import DeviceManagementService, DeviceService, ManagementService, OrganizationService


def test_sqlite_schema_and_relationships() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        org = Organization(name="Example")
        user = User(email="admin@example.test", display_name="Admin", organization=org, status=UserStatus.ACTIVE)
        role = Role(name="operator", organization=org)
        user.roles.append(role)
        device = Device(
            hostname="pc-01",
            device_type="workstation",
            operating_system="Windows",
            organization=org,
            last_seen_at=datetime.now(timezone.utc),
        )
        session.add_all([org, user, role, device])
        session.commit()
        assert user.organization.name == "Example"
        assert user.roles[0].name == "operator"
        assert device.status is DeviceStatus.ACTIVE
        assert isinstance(device.id, uuid.UUID)
        assert org.created_at is not None
        assert org.updated_at is not None
    assert "audit_events" in inspect(engine).get_table_names()


def test_constraints_are_declared() -> None:
    constraints = {constraint.name for constraint in User.__table__.constraints}
    assert "uq_users_org_email" in constraints
    assert "uq_roles_org_name" in {c.name for c in Role.__table__.constraints}


def test_organization_scoped_relationships_round_trip() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc)

    with Session() as session:
        organization = Organization(name="Example")
        user = User(email="admin@example.test", display_name="Admin", organization=organization)
        device = Device(
            hostname="pc-01",
            device_type="workstation",
            operating_system="Windows",
            organization=organization,
        )
        incident = Incident(
            organization=organization,
            device=device,
            assigned_user=user,
            title="Example incident",
            severity=IncidentSeverity.HIGH,
            priority=IncidentPriority.HIGH,
            status=IncidentStatus.OPEN,
            opened_at=now,
        )
        diagnostic_run = DiagnosticRun(
            organization=organization,
            device=device,
            incident=incident,
            diagnostic_type="connectivity",
            status=DiagnosticRunStatus.PENDING,
        )
        recommendation = Recommendation(
            organization=organization,
            device=device,
            incident=incident,
            title="Example recommendation",
            priority=RecommendationPriority.LOW,
            status=RecommendationStatus.PROPOSED,
        )
        repair_action = RepairAction(
            organization=organization,
            device=device,
            incident=incident,
            recommendation=recommendation,
            action_type="verify",
            status=RepairActionStatus.REQUESTED,
            requested_by=user.email,
            requested_at=now,
        )
        escalation = Escalation(
            organization=organization,
            incident=incident,
            escalation_level=1,
            reason="Example escalation",
            status=EscalationStatus.OPEN,
            escalated_at=now,
        )
        session.add_all([organization, user, device, incident, diagnostic_run, recommendation, repair_action, escalation])
        session.commit()

        assert incident.organization is organization
        assert diagnostic_run.organization is organization
        assert recommendation.organization is organization
        assert repair_action.organization is organization
        assert escalation.organization is organization
        assert incident in organization.incidents
        assert diagnostic_run in organization.diagnostic_runs
        assert recommendation in organization.recommendations
        assert repair_action in organization.repair_actions
        assert escalation in organization.escalations


def test_scoped_unique_constraints_are_enforced() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        org = Organization(name="Example")
        session.add_all(
            [
                org,
                User(email="same@example.test", display_name="First", organization=org),
                User(email="same@example.test", display_name="Second", organization=org),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_database_dependency_closes_isolated_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    monkeypatch.setattr("app.db.get_session_factory", lambda: lambda: session)

    dependency = get_db()
    assert next(dependency) is session
    dependency.close()
    session.close.assert_called_once_with()


def test_organization_and_device_services_persist_with_scope() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    organization_service = OrganizationService()
    device_service = DeviceService()

    with Session() as session:
        organization = organization_service.create_organization(session, name="Example")
        other_organization = organization_service.create_organization(session, name="Other")
        device = device_service.create_device(
            session,
            organization_id=organization.id,
            hostname="pc-01",
            device_type="workstation",
            operating_system="Windows",
        )
        other_device = device_service.create_device(
            session,
            organization_id=other_organization.id,
            hostname="pc-01",
            device_type="workstation",
            operating_system="Windows",
        )

        assert organization_service.get_organization(session, organization.id) is organization
        assert organization_service.list_organizations(session) == [organization, other_organization]
        assert device_service.get_device(session, device.id, organization_id=organization.id) is device
        assert device_service.get_device(session, other_device.id, organization_id=organization.id) is None
        assert device_service.list_devices(session, organization_id=organization.id) == [device]

        with pytest.raises(PersistenceError):
            device_service.create_device(
                session,
                organization_id=organization.id,
                hostname="pc-01",
                device_type="server",
                operating_system="Linux",
            )


def test_api_schemas_reject_empty_required_values() -> None:
    with pytest.raises(ValueError):
        OrganizationCreate(name="")
    with pytest.raises(ValueError):
        DeviceCreate(
            organization_id=uuid.uuid4(),
            hostname="",
            device_type="workstation",
            operating_system="Windows",
        )


def test_management_service_is_organization_scoped_and_audited() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    service = ManagementService()

    with Session() as session:
        organization = Organization(name="Managed")
        other_organization = Organization(name="Other")
        actor = User(email="admin@managed.test", display_name="Admin", organization=organization)
        admin_role = Role(name="organization_admin", organization=organization)
        actor.roles.append(admin_role)
        session.add_all([organization, other_organization, actor, admin_role])
        session.commit()

        created = service.create_user(
            session,
            organization_id=organization.id,
            email="user@managed.test",
            display_name="Managed User",
            password="long-enough-password",
            actor=actor,
        )
        assert created.organization_id == organization.id
        assert created.password_hash is not None
        assert service.get_user(session, other_organization.id, created.id) is None
        events, total = service.list_audit_events(
            session, organization.id, offset=0, limit=20, event_type="user_created"
        )
        assert total == 1
        assert events[0].event_metadata["target_user_id"] == str(created.id)


def test_management_service_rejects_platform_role_assignment() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    service = ManagementService()

    with Session() as session:
        organization = Organization(name="Managed")
        actor = User(email="admin@managed.test", display_name="Admin", organization=organization)
        target = User(email="user@managed.test", display_name="User", organization=organization)
        admin_role = Role(name="organization_admin", organization=organization)
        platform_role = Role(name="platform_admin", organization=organization)
        actor.roles.append(admin_role)
        session.add_all([organization, actor, target, admin_role, platform_role])
        session.commit()

        with pytest.raises(SecurityError):
            service.assign_role(session, user=target, role=platform_role, actor=actor)


def test_device_management_is_scoped_filtered_and_audited() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    service = DeviceManagementService()

    with Session() as session:
        organization = Organization(name="Managed")
        other_organization = Organization(name="Other")
        actor = User(email="admin@managed.test", display_name="Admin", organization=organization)
        admin_role = Role(name="organization_admin", organization=organization)
        actor.roles.append(admin_role)
        session.add_all([organization, other_organization, actor, admin_role])
        session.commit()

        managed = service.create_device(
            session,
            organization_id=organization.id,
            actor=actor,
            hostname="managed-pc",
            device_type="workstation",
            operating_system="Windows",
            ip_address="192.0.2.10",
        )
        other = Device(
            organization=other_organization,
            hostname="other-pc",
            device_type="server",
            operating_system="Linux",
            ip_address="192.0.2.20",
        )
        session.add(other)
        session.commit()
        assert service.get_device(session, managed.id, organization.id) is managed
        assert service.get_device(session, other.id, organization.id) is None

        devices, total = service.list_devices(
            session, organization.id, offset=0, limit=10, search="managed"
        )
        assert total == 1
        assert devices == [managed]
        updated = service.update_device(
            session,
            device=managed,
            actor=actor,
            hostname="managed-laptop",
            device_type="laptop",
            operating_system="Windows 11",
            ip_address="192.0.2.11",
        )
        assert updated.hostname == "managed-laptop"
        service.set_status(session, device=managed, actor=actor, status=DeviceStatus.INACTIVE)
        assert managed.status is DeviceStatus.INACTIVE
        inactive, inactive_total = service.list_devices(
            session, organization.id, offset=0, limit=10, status=DeviceStatus.INACTIVE
        )
        assert inactive_total == 1
        assert inactive == [managed]
        events = session.query(AuditEvent).filter_by(resource_type="device").all()
        assert {event.event_type for event in events} == {
            "device_created",
            "device_updated",
            "device_deactivated",
        }


def test_device_management_schema_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        DeviceManagementCreate(
            hostname="host",
            device_type="server",
            operating_system="Linux",
            ip_address="not-an-ip",
        )

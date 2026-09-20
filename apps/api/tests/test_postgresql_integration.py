"""End-to-end validation against an explicitly configured PostgreSQL database."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import (
    AuditEvent,
    Device,
    DeviceStatus,
    DiscoveryJob,
    DiscoveryJobStatus,
    DiscoveryResult,
    DiscoveryResultStatus,
    DiagnosticResult,
    DiagnosticResultSeverity,
    DiagnosticResultStatus,
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
    ReconciliationStatus,
    RepairAction,
    RepairActionStatus,
    Role,
    User,
    UserStatus,
)


def _postgresql_url() -> str | None:
    """Only opt in to a separately named PostgreSQL test database."""
    url = os.getenv("TEST_DATABASE_URL")
    if url and url.split(":", 1)[0].lower().startswith("postgresql"):
        return url
    return None


POSTGRESQL_URL = _postgresql_url()
pytestmark = pytest.mark.postgresql


@pytest.fixture
def postgresql_database(monkeypatch: pytest.MonkeyPatch):
    if POSTGRESQL_URL is None:
        pytest.skip("Set TEST_DATABASE_URL to an explicit isolated PostgreSQL URL")

    # Alembic is environment-driven and only accepts DATABASE_URL. Prefer the
    # test-specific variable without ever falling back to an implicit database.
    monkeypatch.setenv("DATABASE_URL", POSTGRESQL_URL)
    get_settings.cache_clear()
    root = Path(__file__).resolve().parents[3]
    alembic_config = Config(str(root / "alembic.ini"))

    # Establish a known lifecycle, then leave the isolated test database clean.
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    engine = create_engine(POSTGRESQL_URL)
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_postgresql_migration_and_persistence_lifecycle(postgresql_database) -> None:
    engine = postgresql_database
    expected_tables = {
        "organizations",
        "users",
        "roles",
        "user_roles",
        "devices",
        "incidents",
        "diagnostic_runs",
        "diagnostic_results",
        "recommendations",
        "repair_actions",
        "escalations",
        "audit_events",
        "discovery_jobs",
        "discovery_results",
    }
    assert expected_tables.issubset(set(inspect(engine).get_table_names()))

    Session = sessionmaker(bind=engine)
    organization_id = uuid.uuid4()
    with Session() as session:
        organization = Organization(id=organization_id, name="PostgreSQL Integration")
        user = User(
            email="admin@integration.test",
            display_name="Integration Admin",
            organization=organization,
            status=UserStatus.ACTIVE,
        )
        role = Role(name="operator", organization=organization)
        user.roles.append(role)
        device = Device(
            hostname="integration-pg-01",
            device_type="workstation",
            operating_system="Linux",
            organization=organization,
            status=DeviceStatus.ACTIVE,
            last_seen_at=datetime.now(timezone.utc),
        )
        incident = Incident(
            organization=organization,
            device=device,
            assigned_user=user,
            title="Integration incident",
            description="PostgreSQL persistence validation",
            severity=IncidentSeverity.HIGH,
            priority=IncidentPriority.HIGH,
            status=IncidentStatus.OPEN,
            opened_at=datetime.now(timezone.utc),
        )
        diagnostic_run = DiagnosticRun(
            organization=organization,
            device=device,
            incident=incident,
            diagnostic_type="connectivity",
            status=DiagnosticRunStatus.PENDING,
        )
        diagnostic_result = DiagnosticResult(
            diagnostic_run=diagnostic_run,
            check_identifier="network.reachability",
            status=DiagnosticResultStatus.PASS,
            severity=DiagnosticResultSeverity.INFO,
            observed_value={"reachable": True},
            expected_value={"reachable": True},
            message="Reachability check passed",
            evidence="integration-test",
        )
        recommendation = Recommendation(
            organization=organization,
            device=device,
            incident=incident,
            diagnostic_result=diagnostic_result,
            title="No action required",
            description="The check passed.",
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
            requested_at=datetime.now(timezone.utc),
            verification_result={"verified": False},
        )
        escalation = Escalation(
            organization=organization,
            incident=incident,
            escalation_level=1,
            reason="Integration validation",
            status=EscalationStatus.OPEN,
            assigned_to=user.email,
            escalated_at=datetime.now(timezone.utc),
        )
        discovery_job = DiscoveryJob(
            organization=organization,
            created_by_user_id=user.id,
            provider="simulated",
            target_type="address",
            target_definition="192.0.2.10",
            target_count=1,
            status=DiscoveryJobStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )
        discovery_result = DiscoveryResult(
            job=discovery_job,
            organization=organization,
            target_ip="192.0.2.10",
            discovered_hostname=device.hostname,
            discovered_device_type=device.device_type,
            discovered_operating_system=device.operating_system,
            provider="simulated",
            status=DiscoveryResultStatus.DISCOVERED,
            reconciliation_status=ReconciliationStatus.MATCHED,
            matched_device_id=device.id,
            discovered_at=datetime.now(timezone.utc),
            result_metadata={"simulation": True},
        )
        session.add_all(
            [
                organization,
                user,
                role,
                device,
                incident,
                diagnostic_run,
                diagnostic_result,
                recommendation,
                repair_action,
                escalation,
                discovery_job,
                discovery_result,
            ]
        )
        session.flush()
        audit_event = AuditEvent(
            organization_id=organization.id,
            actor_user_id=user.id,
            event_type="integration_test",
            resource_type="device",
            resource_id=str(device.id),
            action="create",
            result="success",
            event_metadata={"source": "pytest", "checks": ["uuid", "json", "fk"]},
            created_at=datetime.now(timezone.utc),
        )
        session.add(audit_event)
        session.commit()
        session.refresh(audit_event)

        assert isinstance(organization.id, uuid.UUID)
        assert organization.created_at.tzinfo is not None
        assert device.organization is organization
        assert user.roles[0].name == "operator"
        assert diagnostic_result.diagnostic_run is diagnostic_run
        assert recommendation.diagnostic_result is diagnostic_result
        assert repair_action.recommendation is recommendation
        assert escalation.incident is incident
        assert discovery_result.job is discovery_job
        assert discovery_result.matched_device_id == device.id
        assert audit_event.event_metadata == {"source": "pytest", "checks": ["uuid", "json", "fk"]}

        session.add(User(email="admin@integration.test", display_name="Duplicate", organization=organization))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Device(
                hostname="orphan",
                device_type="workstation",
                operating_system="Linux",
                organization_id=uuid.uuid4(),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    # Verify the downgrade lifecycle removes the schema, not just the data.
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    command.downgrade(config, "base")
    try:
        assert "organizations" not in inspect(engine).get_table_names()
    finally:
        command.upgrade(config, "head")

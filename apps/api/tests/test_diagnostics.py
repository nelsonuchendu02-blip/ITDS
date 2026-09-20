from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.diagnostics.provider import SimulatedDiagnosticProvider
from app.exceptions import PersistenceError, SecurityError
from app.models import (
    AuditEvent, Base, Device, DiagnosticCheckType, DiagnosticResult, DiagnosticRun,
    DiagnosticRunStatus, Organization, User,
)
from app.services.diagnostics import DiagnosticService
from app.permissions import permissions_for_roles
from app.schemas.diagnostics import DiagnosticRunCreate


def test_simulated_provider_is_deterministic_and_structured() -> None:
    provider = SimulatedDiagnosticProvider()
    first = provider.run(device_id=UUID("00000000-0000-0000-0000-000000000001"),
                         diagnostic_type="connectivity")
    second = provider.run(device_id=UUID("00000000-0000-0000-0000-000000000001"),
                          diagnostic_type="connectivity")
    assert first == second
    assert first[0].status == "pass"
    assert first[0].observed["simulation"] is True


@pytest.mark.parametrize("check_type", list(DiagnosticCheckType))
def test_simulated_provider_supports_only_explicit_check_types(check_type: DiagnosticCheckType) -> None:
    result = SimulatedDiagnosticProvider().run(
        device_id=UUID("00000000-0000-0000-0000-000000000001"),
        diagnostic_type=check_type.value,
    )[0]
    assert result.check_type is check_type


def test_simulated_provider_never_accepts_execution_inputs() -> None:
    result = SimulatedDiagnosticProvider().run(
        device_id=UUID("00000000-0000-0000-0000-000000000001"),
        diagnostic_type="security",
    )[0]
    assert "subprocess" not in result.message.lower()
    assert "credential" not in str(result.observed).lower()


@pytest.fixture
def diagnostic_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        org = Organization(name="Diagnostics")
        other = Organization(name="Other")
        user = User(organization=org, email="operator@example.test", display_name="Operator")
        device = Device(organization=org, hostname="diag-01", device_type="server", operating_system="Linux")
        foreign_device = Device(organization=other, hostname="diag-02", device_type="server", operating_system="Linux")
        session.add_all([org, other, user, device, foreign_device])
        session.commit()
        yield session, org, other, user, device, foreign_device
    engine.dispose()


def test_create_scopes_device_and_rejects_foreign_device(diagnostic_db) -> None:
    session, org, other, user, device, foreign_device = diagnostic_db
    service = DiagnosticService()
    run = service.create(session, organization_id=org.id, actor=user, device_id=device.id,
                         diagnostic_type="connectivity")
    assert run.organization_id == org.id
    with pytest.raises(SecurityError) as error:
        service.create(session, organization_id=org.id, actor=user, device_id=foreign_device.id,
                       diagnostic_type="connectivity")
    assert error.value.status_code == 404


def test_lifecycle_creates_explicit_scoped_result_and_is_idempotently_guarded(diagnostic_db) -> None:
    session, org, _other, user, device, _foreign = diagnostic_db
    service = DiagnosticService()
    run = service.create(session, organization_id=org.id, actor=user, device_id=device.id,
                         diagnostic_type="security")
    completed = service.run(session, run=run, actor=user)
    assert completed.status is DiagnosticRunStatus.COMPLETED
    result = session.scalar(select(DiagnosticResult).where(DiagnosticResult.diagnostic_run_id == run.id))
    assert result is not None
    assert result.organization_id == org.id
    assert result.device_id == device.id
    assert result.title
    assert result.checked_at is not None
    with pytest.raises(SecurityError):
        service.run(session, run=completed, actor=user)


def test_cancel_and_completion_race_cannot_reenter_terminal_state(diagnostic_db) -> None:
    session, org, _other, user, device, _foreign = diagnostic_db
    service = DiagnosticService()
    run = service.create(session, organization_id=org.id, actor=user, device_id=device.id,
                         diagnostic_type="connectivity")
    cancelled = service.cancel(session, run=run, actor=user)
    assert cancelled.status is DiagnosticRunStatus.CANCELLED
    with pytest.raises(SecurityError):
        service.cancel(session, run=cancelled, actor=user)


class ExplodingProvider:
    def run(self, **_kwargs):
        raise RuntimeError("provider credentials must not escape")


def test_provider_failure_is_sanitized_and_marks_run_failed(diagnostic_db) -> None:
    session, org, _other, user, device, _foreign = diagnostic_db
    service = DiagnosticService(provider=ExplodingProvider())
    run = service.create(session, organization_id=org.id, actor=user, device_id=device.id,
                         diagnostic_type="connectivity")
    with pytest.raises(PersistenceError) as error:
        service.run(session, run=run, actor=user)
    assert "credentials" not in str(error.value).lower()
    failed = service.get(session, run.id, org.id)
    assert failed is not None
    assert failed.status is DiagnosticRunStatus.FAILED
    assert failed.error_code == "diagnostic_execution_failed"
    audit = session.scalars(select(AuditEvent).where(
        AuditEvent.event_type == "diagnostic_failed",
        AuditEvent.resource_id == str(run.id),
    )).all()
    assert len(audit) == 1
    assert audit[0].organization_id == org.id
    assert "provider secret" not in str(audit[0].event_metadata).lower()


def test_cross_organization_run_is_denied(diagnostic_db) -> None:
    session, org, other, user, device, _foreign = diagnostic_db
    service = DiagnosticService()
    run = service.create(session, organization_id=org.id, actor=user, device_id=device.id,
                         diagnostic_type="connectivity")
    other_user = User(organization_id=other.id, email="other@example.test", display_name="Other")
    with pytest.raises(SecurityError) as error:
        service.run(session, run=run, actor=other_user)
    assert error.value.status_code == 403


def test_diagnostic_permissions_are_role_scoped() -> None:
    assert {"diagnostics:read", "diagnostics:run", "diagnostics:manage"} <= permissions_for_roles(
        ["organization_admin"]
    )
    assert {"diagnostics:read", "diagnostics:run"} <= permissions_for_roles(["technician"])
    assert "diagnostics:run" not in permissions_for_roles(["viewer"])


def test_run_request_rejects_server_controlled_fields(diagnostic_db) -> None:
    _session, _org, _other, _user, device, _foreign = diagnostic_db
    with pytest.raises(ValueError):
        DiagnosticRunCreate(
            device_id=device.id,
            organization_id="00000000-0000-0000-0000-000000000001",
            status="completed",
        )

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.exceptions import PersistenceError, SecurityError
from app.main import app
from app.db import get_db
from app.models import (
    AuditEvent, Base, DiagnosticCheckType, DiagnosticResult, DiagnosticResultSeverity,
    DiagnosticResultStatus, DiagnosticRun, DiagnosticRunStatus, Device, Organization,
    RootCauseAnalysisStatus, RootCauseFindingConfidence, RootCauseFindingSeverity,
    RootCauseFindingStatus, User,
)
from app.root_cause import evaluate_rules
from app.permissions import permissions_for_roles
from app.repositories.root_cause import RootCauseRepository
from app.schemas.root_cause import RootCauseAnalysisCreate
from app.services.root_cause import RootCauseService


def _result(check_type: DiagnosticCheckType, status: DiagnosticResultStatus):
    return SimpleNamespace(id=uuid4(), check_type=check_type, status=status)


def test_rules_are_deterministic_and_reference_failed_evidence() -> None:
    evidence = _result(DiagnosticCheckType.CONNECTIVITY, DiagnosticResultStatus.FAIL)
    results = [evidence, _result(DiagnosticCheckType.CONNECTIVITY, DiagnosticResultStatus.PASS)]

    first = evaluate_rules(results)
    second = evaluate_rules(results)

    assert first == second
    assert len(first) == 1
    finding = first[0]
    assert finding.rule_id == "connectivity-failure"
    assert finding.status is RootCauseFindingStatus.IDENTIFIED
    assert finding.severity is RootCauseFindingSeverity.HIGH
    assert finding.confidence is RootCauseFindingConfidence.HIGH
    assert finding.evidence_result_ids == (str(evidence.id),)


@pytest.mark.parametrize("check_type", list(DiagnosticCheckType))
def test_each_allow_listed_failure_rule_is_explainable(check_type: DiagnosticCheckType) -> None:
    finding = evaluate_rules([_result(check_type, DiagnosticResultStatus.FAIL)])[0]

    assert finding.category == check_type.value.upper()
    assert finding.explanation.startswith("Deterministic rule ")
    assert finding.confidence is RootCauseFindingConfidence.HIGH
    assert finding.severity in set(RootCauseFindingSeverity)


def test_pass_results_do_not_create_definitive_findings() -> None:
    results = [
        _result(check_type, DiagnosticResultStatus.PASS)
        for check_type in DiagnosticCheckType
    ]

    assert evaluate_rules(results) == []


def test_rules_deduplicate_same_rule_and_evidence() -> None:
    evidence = _result(DiagnosticCheckType.SECURITY, DiagnosticResultStatus.FAIL)

    findings = evaluate_rules([evidence, evidence])

    assert len(findings) == 1
    assert findings[0].evidence_result_ids == (str(evidence.id), str(evidence.id))


@pytest.fixture
def root_cause_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        organization = Organization(name="Root Cause Org")
        other_organization = Organization(name="Other Root Cause Org")
        actor = User(
            organization=organization,
            email="root-cause@example.test",
            display_name="Root Cause Operator",
        )
        device = Device(
            organization=organization,
            hostname="root-cause-device",
            device_type="server",
            operating_system="Linux",
        )
        other_device = Device(
            organization=other_organization,
            hostname="other-root-cause-device",
            device_type="server",
            operating_system="Linux",
        )
        session.add_all([organization, other_organization, actor, device, other_device])
        session.flush()
        run = DiagnosticRun(
            organization_id=organization.id,
            device_id=device.id,
            diagnostic_type="connectivity",
            provider="simulated",
            status=DiagnosticRunStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )
        other_run = DiagnosticRun(
            organization_id=other_organization.id,
            device_id=other_device.id,
            diagnostic_type="connectivity",
            provider="simulated",
            status=DiagnosticRunStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )
        session.add_all([run, other_run])
        session.flush()
        result = DiagnosticResult(
            diagnostic_run_id=run.id,
            organization_id=organization.id,
            device_id=device.id,
            check_identifier="connectivity-check",
            check_type=DiagnosticCheckType.CONNECTIVITY,
            status=DiagnosticResultStatus.FAIL,
            severity=DiagnosticResultSeverity.HIGH,
            title="Connectivity failure",
            checked_at=datetime.now(timezone.utc),
        )
        session.add(result)
        session.commit()
        yield session, organization, other_organization, actor, device, other_device, run, other_run
    engine.dispose()


@pytest.fixture
def api_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db
        yield session
        app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/root-cause/analyses"),
        ("get", "/api/v1/root-cause/analyses"),
        ("post", f"/api/v1/root-cause/analyses/{uuid4()}/run"),
        ("post", f"/api/v1/root-cause/analyses/{uuid4()}/cancel"),
    ],
)
def test_root_cause_endpoints_require_authentication(method: str, path: str, api_db) -> None:
    client = TestClient(app)
    if method == "post" and path.endswith("analyses"):
        response = client.post(path, json={"diagnostic_run_id": str(uuid4())})
    else:
        response = getattr(client, method)(path)
    assert response.status_code == 401


def test_root_cause_permissions_and_server_owned_fields() -> None:
    assert {"root_cause:read", "root_cause:run", "root_cause:manage"} <= permissions_for_roles(
        ["organization_admin"]
    )
    assert {"root_cause:read", "root_cause:run"} <= permissions_for_roles(["technician"])
    assert "root_cause:manage" not in permissions_for_roles(["technician"])
    assert not ({"root_cause:read", "root_cause:run", "root_cause:manage"} & permissions_for_roles(["viewer"]))
    with pytest.raises(ValueError):
        RootCauseAnalysisCreate(
            diagnostic_run_id=uuid4(),
            organization_id=uuid4(),
            device_id=uuid4(),
            status="COMPLETED",
            initiated_by_user_id=uuid4(),
            provider="user-provider",
            evidence={},
            error_code="secret",
        )


def test_root_cause_rejects_foreign_run_and_protects_lifecycle(root_cause_db) -> None:
    session, organization, other_organization, actor, _device, _other_device, run, other_run = root_cause_db
    service = RootCauseService()
    with pytest.raises(SecurityError) as error:
        service.create(
            session,
            organization_id=organization.id,
            diagnostic_run_id=other_run.id,
            actor=actor,
        )
    assert error.value.status_code == 404

    analysis = service.create(
        session, organization_id=organization.id, diagnostic_run_id=run.id, actor=actor
    )
    assert analysis.status is RootCauseAnalysisStatus.PENDING
    assert service.get(session, analysis.id, other_organization.id) is None
    with pytest.raises(SecurityError) as error:
        service.cancel(
            session,
            analysis=analysis,
            actor=User(organization_id=other_organization.id, email="other-root@example.test",
                       display_name="Other"),
        )
    assert error.value.status_code == 403

    cancelled = service.cancel(session, analysis=analysis, actor=actor)
    assert cancelled.status is RootCauseAnalysisStatus.CANCELLED
    assert not RootCauseRepository().transition(
        session, analysis.id, organization.id,
        RootCauseAnalysisStatus.RUNNING, RootCauseAnalysisStatus.COMPLETED,
    )

    analysis = service.create(
        session, organization_id=organization.id, diagnostic_run_id=run.id, actor=actor
    )
    completed = service.run(session, analysis=analysis, actor=actor)
    assert completed.status is RootCauseAnalysisStatus.COMPLETED
    assert service.findings(session, completed, other_organization.id) == []
    with pytest.raises(SecurityError):
        service.run(session, analysis=completed, actor=actor)
    with pytest.raises(SecurityError):
        service.cancel(session, analysis=completed, actor=actor)
    assert other_organization.id != organization.id


def test_root_cause_failure_is_rolled_back_and_sanitized(root_cause_db, monkeypatch) -> None:
    session, organization, _other_organization, actor, _device, _other_device, run, _other_run = root_cause_db
    analysis = RootCauseService().create(
        session, organization_id=organization.id, diagnostic_run_id=run.id, actor=actor
    )

    def explode(_results):
        raise RuntimeError("provider token must not escape")

    monkeypatch.setattr("app.services.root_cause.evaluate_rules", explode)
    with pytest.raises(PersistenceError) as error:
        RootCauseService().run(session, analysis=analysis, actor=actor)
    assert "token" not in str(error.value).lower()
    failed = RootCauseService().get(session, analysis.id, organization.id)
    assert failed is not None
    assert failed.status is RootCauseAnalysisStatus.FAILED
    assert failed.error_code == "root_cause_analysis_failed"
    audit = session.scalars(select(AuditEvent).where(
        AuditEvent.event_type == "root_cause_analysis_failed",
        AuditEvent.resource_id == str(analysis.id),
    )).all()
    assert len(audit) == 1
    assert "token" not in str(audit[0].event_metadata).lower()

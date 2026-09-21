from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.exceptions import SecurityError
from app.models import (
    Base, DiagnosticResult, DiagnosticResultSeverity, DiagnosticResultStatus,
    Device, DiagnosticCheckType, DiagnosticRun, DiagnosticRunStatus, Organization, RecommendationStatus,
    Recommendation,     RootCauseAnalysis, RootCauseAnalysisStatus, RootCauseFinding, RootCauseFindingConfidence, RootCauseFindingSeverity,
    RootCauseFindingStatus, User,
)
from app.permissions import permissions_for_roles
from app.services.recommendation import RecommendationService


@pytest.fixture
def recommendation_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        org = Organization(name="Recommendation Org")
        other = Organization(name="Other Org")
        actor = User(organization=org, email="recommend@example.test", display_name="Operator")
        device = Device(organization=org, hostname="recommend-device", device_type="server", operating_system="Linux")
        session.add_all([org, other, actor, device])
        session.flush()
        run = DiagnosticRun(
            organization_id=org.id, device_id=device.id, diagnostic_type="security",
            status=DiagnosticRunStatus.COMPLETED,
        )
        session.add(run)
        session.flush()
        analysis = RootCauseAnalysis(
            organization_id=org.id, device_id=device.id, diagnostic_run_id=run.id,
            status=RootCauseAnalysisStatus.COMPLETED,
        )
        session.add(analysis)
        session.flush()
        result = DiagnosticResult(
            organization_id=org.id, device_id=device.id, diagnostic_run_id=run.id,
            check_identifier="security-check", check_type=DiagnosticCheckType.SECURITY,
            status=DiagnosticResultStatus.FAIL, severity=DiagnosticResultSeverity.HIGH,
            title="Security failure", checked_at=datetime.now(timezone.utc),
        )
        session.add(result)
        session.flush()
        finding = RootCauseFinding(
            organization_id=org.id, device_id=device.id, diagnostic_result_id=result.id,
            analysis_id=analysis.id, rule_id="security-failure", category="SECURITY",
            status=RootCauseFindingStatus.IDENTIFIED, severity=RootCauseFindingSeverity.HIGH,
            confidence=RootCauseFindingConfidence.HIGH, title="Fix security",
            summary="Fix security", explanation="Deterministic", evidence={}, fingerprint="security:1",
        )
        session.add(finding)
        session.commit()
        yield session, org, other, actor, finding
    engine.dispose()


def test_recommendation_is_scoped_and_lifecycle_is_guarded(recommendation_db):
    session, org, other, actor, finding = recommendation_db
    service = RecommendationService()
    recommendation = service.create(
        session, organization_id=org.id, actor=actor, finding_id=finding.id,
        title="Apply security fix", description="A safe fix", priority="high",
        rationale="Evidence-backed",
    )
    assert recommendation.status is RecommendationStatus.PROPOSED
    assert recommendation.title == "Remediate security control failure"
    assert recommendation.priority.value == "high"
    assert recommendation.category == "SECURITY"
    assert recommendation.severity.value == "high"
    assert recommendation.summary == finding.summary
    assert recommendation.expected_effect
    assert recommendation.confidence == "high"
    assert recommendation.remediation_type.value == "guidance"
    assert recommendation.requires_human_approval is True
    assert service.get(session, recommendation.id, other.id) is None
    reviewed = service.transition(session, recommendation=recommendation, actor=actor,
                                  target=RecommendationStatus.REVIEWED)
    accepted = service.transition(session, recommendation=reviewed, actor=actor,
                                  target=RecommendationStatus.ACCEPTED)
    assert accepted.status is RecommendationStatus.ACCEPTED
    completed = service.transition(session, recommendation=accepted, actor=actor,
                                   target=RecommendationStatus.IMPLEMENTED)
    assert completed.status is RecommendationStatus.IMPLEMENTED
    with pytest.raises(SecurityError):
        service.transition(session, recommendation=completed, actor=actor,
                           target=RecommendationStatus.REJECTED)


def test_foreign_finding_is_not_disclosed(recommendation_db):
    session, org, _other, actor, _finding = recommendation_db
    with pytest.raises(SecurityError) as error:
        RecommendationService().create(
            session, organization_id=org.id, actor=actor, finding_id=uuid4(),
            title="No access", description=None, priority="low", rationale=None,
        )
    assert error.value.status_code == 404


def test_generation_uses_registry_and_is_idempotent(recommendation_db):
    session, org, _other, actor, finding = recommendation_db
    service = RecommendationService()
    first = service.generate(session, organization_id=org.id, actor=actor,
                             analysis_id=finding.analysis_id)
    assert len(first) == 1
    assert first[0].rule_id == "security-failure"
    assert first[0].status is RecommendationStatus.PENDING
    assert service.generate(session, organization_id=org.id, actor=actor,
                            analysis_id=finding.analysis_id) == []


def test_deduplication_identity_allows_distinct_rules_and_evidence(recommendation_db):
    session, org, _other, actor, finding = recommendation_db
    service = RecommendationService()
    assert len(service.generate(
        session, organization_id=org.id, actor=actor, analysis_id=finding.analysis_id,
    )) == 1
    finding.rule_id = "configuration-failure"
    session.commit()
    assert len(service.generate(
        session, organization_id=org.id, actor=actor, analysis_id=finding.analysis_id,
    )) == 1
    finding.rule_id = "security-failure"
    finding.fingerprint = "security:materially-different-evidence"
    session.commit()
    assert len(service.generate(
        session, organization_id=org.id, actor=actor, analysis_id=finding.analysis_id,
    )) == 1
    assert len(service.generate(
        session, organization_id=org.id, actor=actor, analysis_id=finding.analysis_id,
    )) == 0


def test_priority_calculation_is_bounded_and_deterministic(recommendation_db):
    session, org, _other, actor, finding = recommendation_db
    service = RecommendationService()
    first = service.generate(
        session, organization_id=org.id, actor=actor, analysis_id=finding.analysis_id,
    )[0]
    assert service._fingerprint(
        organization_id=org.id, device_id=finding.device_id,
        finding_id=finding.id, rule_id=first.rule_id, evidence=first.evidence,
    ) == first.fingerprint
    assert first.priority.value in {"low", "medium", "high"}


def test_recommendation_permissions_are_separated():
    assert {"recommendations:read", "recommendations:run", "recommendations:manage"} <= permissions_for_roles(["organization_admin"])
    assert "recommendations:manage" not in permissions_for_roles(["technician"])


def test_database_rejects_cross_organization_recommendation_links(recommendation_db):
    session, org, other, actor, finding = recommendation_db
    session.commit()
    session.connection().exec_driver_sql("PRAGMA foreign_keys=ON")
    other_device = Device(
        organization_id=other.id, hostname="other-device", device_type="server",
        operating_system="Linux",
    )
    session.add(other_device)
    session.flush()
    invalid = Recommendation(
        organization_id=org.id,
        device_id=other_device.id,
        diagnostic_result_id=finding.diagnostic_result_id,
        root_cause_finding_id=finding.id,
        title="Invalid link",
        priority="high",
        status=RecommendationStatus.PENDING,
        rule_id="security-failure",
        category="SECURITY",
        severity="high",
        summary="invalid",
        expected_effect="none",
        confidence="high",
        remediation_type="guidance",
        requires_human_approval=True,
        evidence={},
    )
    session.add(invalid)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_database_rejects_analysis_finding_result_and_device_mismatches(recommendation_db):
    session, org, other, _actor, finding = recommendation_db
    other_device = Device(
        organization_id=other.id, hostname="other-matrix-device",
        device_type="server", operating_system="Linux",
    )
    session.add(other_device)
    session.flush()
    other_run = DiagnosticRun(
        organization_id=other.id, device_id=other_device.id,
        diagnostic_type="security", status=DiagnosticRunStatus.COMPLETED,
    )
    session.add(other_run)
    session.flush()
    other_analysis = RootCauseAnalysis(
        organization_id=other.id, device_id=other_device.id,
        diagnostic_run_id=other_run.id, status=RootCauseAnalysisStatus.COMPLETED,
    )
    session.add(other_analysis)
    session.flush()
    other_result = DiagnosticResult(
        organization_id=other.id, device_id=other_device.id,
        diagnostic_run_id=other_run.id, check_identifier="other-security",
        check_type=DiagnosticCheckType.SECURITY, status=DiagnosticResultStatus.FAIL,
        severity=DiagnosticResultSeverity.HIGH, title="Other failure",
        checked_at=datetime.now(timezone.utc),
    )
    session.add(other_result)
    session.flush()
    other_finding = RootCauseFinding(
        organization_id=other.id, device_id=other_device.id,
        diagnostic_result_id=other_result.id, analysis_id=other_analysis.id,
        rule_id="security-failure", category="SECURITY",
        status=RootCauseFindingStatus.IDENTIFIED,
        severity=RootCauseFindingSeverity.HIGH,
        confidence=RootCauseFindingConfidence.HIGH, title="Other finding",
        summary="Other summary", explanation="Other explanation",
        evidence={}, fingerprint="other-security",
    )
    session.add(other_finding)
    session.flush()
    session.commit()
    session.connection().exec_driver_sql("PRAGMA foreign_keys=ON")
    invalid_links = (
        {"organization_id": org.id, "device_id": other_device.id,
         "root_cause_analysis_id": finding.analysis_id,
         "root_cause_finding_id": finding.id,
         "diagnostic_result_id": finding.diagnostic_result_id},
        {"organization_id": org.id, "device_id": finding.device_id,
         "root_cause_analysis_id": other_analysis.id,
         "root_cause_finding_id": other_finding.id,
         "diagnostic_result_id": other_result.id},
        {"organization_id": org.id, "device_id": finding.device_id,
         "root_cause_analysis_id": finding.analysis_id,
         "root_cause_finding_id": other_finding.id,
         "diagnostic_result_id": finding.diagnostic_result_id},
        {"organization_id": org.id, "device_id": finding.device_id,
         "root_cause_analysis_id": finding.analysis_id,
         "root_cause_finding_id": finding.id,
         "diagnostic_result_id": other_result.id},
    )
    for values in invalid_links:
        invalid = Recommendation(
            **values, title="Invalid matrix link", rule_id="security-failure",
            fingerprint=str(uuid4()), category="SECURITY", severity="high",
            summary="invalid", expected_effect="none", confidence="high",
            remediation_type="guidance", requires_human_approval=True,
            evidence={}, priority="high", status=RecommendationStatus.PENDING,
        )
        session.add(invalid)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

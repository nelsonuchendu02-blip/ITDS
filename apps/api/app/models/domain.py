"""SQLAlchemy domain models for the Phase 1A persistence foundation."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON,
    String, Text, UniqueConstraint, event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, uuid_pk
from .enums import (
    DeviceStatus,
    DiagnosticResultSeverity,
    DiagnosticResultStatus,
    DiagnosticRunStatus,
    DiagnosticCheckType,
    DiscoveryJobStatus,
    DiscoveryResultStatus,
    EscalationStatus,
    IncidentPriority,
    IncidentSeverity,
    IncidentStatus,
    OrganizationStatus,
    RecommendationConfidence,
    RecommendationPriority,
    RecommendationRemediationType,
    RecommendationSeverity,
    RecommendationStatus,
    RepairActionStatus,
    ReconciliationStatus,
    RootCauseAnalysisStatus,
    RootCauseFindingConfidence,
    RootCauseFindingSeverity,
    RootCauseFindingStatus,
    UserStatus,
)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, name="organization_status"), default=OrganizationStatus.ACTIVE, nullable=False, index=True
    )
    users: Mapped[list["User"]] = relationship(back_populates="organization")
    roles: Mapped[list["Role"]] = relationship(back_populates="organization")
    devices: Mapped[list["Device"]] = relationship(back_populates="organization")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="organization")
    diagnostic_runs: Mapped[list["DiagnosticRun"]] = relationship(back_populates="organization")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="organization")
    repair_actions: Mapped[list["RepairAction"]] = relationship(back_populates="organization")
    escalations: Mapped[list["Escalation"]] = relationship(back_populates="organization")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="organization")
    discovery_jobs: Mapped[list["DiscoveryJob"]] = relationship(back_populates="organization")
    discovery_results: Mapped[list["DiscoveryResult"]] = relationship(back_populates="organization")
    root_cause_analyses: Mapped[list["RootCauseAnalysis"]] = relationship(back_populates="organization")


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_roles_org_name"),)
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    organization: Mapped[Organization] = relationship(back_populates="roles")
    users: Mapped[list["User"]] = relationship(secondary="user_roles", back_populates="roles")


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_users_org_email"),)
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.ACTIVE, nullable=False, index=True
    )
    organization: Mapped[Organization] = relationship(back_populates="users")
    roles: Mapped[list[Role]] = relationship(secondary="user_roles", back_populates="users")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_devices_id_organization"),
        UniqueConstraint("organization_id", "hostname", name="uq_devices_org_hostname"),
        Index("ix_devices_last_seen_at", "last_seen_at"),
    )
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    device_type: Mapped[str] = mapped_column(String(100), nullable=False)
    operating_system: Mapped[str] = mapped_column(String(200), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="device_status"), default=DeviceStatus.ACTIVE, nullable=False, index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organization: Mapped[Organization] = relationship(back_populates="devices")


class DiscoveryJob(TimestampMixin, Base):
    __tablename__ = "discovery_jobs"
    __table_args__ = (
        Index("ix_discovery_jobs_org_status", "organization_id", "status"),
        Index("ix_discovery_jobs_created_at", "created_at"),
    )
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id: Mapped = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_definition: Mapped[str] = mapped_column(String(255), nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DiscoveryJobStatus] = mapped_column(
        Enum(DiscoveryJobStatus, name="discovery_job_status"), default=DiscoveryJobStatus.PENDING, nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    organization: Mapped[Organization] = relationship(back_populates="discovery_jobs")
    results: Mapped[list["DiscoveryResult"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class DiscoveryResult(TimestampMixin, Base):
    __tablename__ = "discovery_results"
    __table_args__ = (
        Index("ix_discovery_results_job", "discovery_job_id"),
        Index("ix_discovery_results_org_ip", "organization_id", "target_ip"),
        Index("ix_discovery_results_reconciliation", "organization_id", "reconciliation_status"),
    )
    id: Mapped = uuid_pk()
    discovery_job_id: Mapped = mapped_column(ForeignKey("discovery_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    target_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    discovered_hostname: Mapped[str | None] = mapped_column(String(255))
    discovered_device_type: Mapped[str | None] = mapped_column(String(100))
    discovered_operating_system: Mapped[str | None] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[DiscoveryResultStatus] = mapped_column(
        Enum(DiscoveryResultStatus, name="discovery_result_status"), nullable=False
    )
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus, name="reconciliation_status"), nullable=False
    )
    matched_device_id: Mapped = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    job: Mapped[DiscoveryJob] = relationship(back_populates="results")
    organization: Mapped[Organization] = relationship(back_populates="discovery_results")


class Incident(TimestampMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_status_severity_priority", "status", "severity", "priority"),
        Index("ix_incidents_opened_at", "opened_at"),
    )
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_user_id: Mapped = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Diagnostic result")
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity, name="incident_severity"), default=IncidentSeverity.MEDIUM, nullable=False, index=True
    )
    priority: Mapped[IncidentPriority] = mapped_column(
        Enum(IncidentPriority, name="incident_priority"), default=IncidentPriority.MEDIUM, nullable=False, index=True
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status"), default=IncidentStatus.OPEN, nullable=False, index=True
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organization: Mapped[Organization] = relationship(back_populates="incidents")
    device: Mapped[Device | None] = relationship(foreign_keys=[device_id])
    assigned_user: Mapped[User | None] = relationship()


class DiagnosticRun(TimestampMixin, Base):
    __tablename__ = "diagnostic_runs"
    __table_args__ = (
        Index("ix_diagnostic_runs_status_started_at", "status", "started_at"),
        UniqueConstraint(
            "id", "device_id", "organization_id",
            name="uq_diagnostic_runs_id_device_organization",
        ),
    )
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id: Mapped = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    diagnostic_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="simulated")
    created_by_user_id: Mapped = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[DiagnosticRunStatus] = mapped_column(
        Enum(DiagnosticRunStatus, name="diagnostic_run_status"), default=DiagnosticRunStatus.PENDING, nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    organization: Mapped[Organization] = relationship(back_populates="diagnostic_runs")
    device: Mapped[Device] = relationship()
    incident: Mapped[Incident | None] = relationship()


class DiagnosticResult(TimestampMixin, Base):
    __tablename__ = "diagnostic_results"
    __table_args__ = (
        UniqueConstraint(
            "id", "device_id", "organization_id",
            name="uq_diagnostic_results_id_device_organization",
        ),
    )
    id: Mapped = uuid_pk()
    diagnostic_run_id: Mapped = mapped_column(ForeignKey("diagnostic_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    check_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    check_type: Mapped[DiagnosticCheckType] = mapped_column(
        Enum(DiagnosticCheckType, name="diagnostic_check_type"), nullable=False,
        default=DiagnosticCheckType.CONNECTIVITY,
    )
    status: Mapped[DiagnosticResultStatus] = mapped_column(
        Enum(DiagnosticResultStatus, name="diagnostic_result_status"), nullable=False
    )
    severity: Mapped[DiagnosticResultSeverity] = mapped_column(
        Enum(DiagnosticResultSeverity, name="diagnostic_result_severity"), nullable=False
    )
    observed_value: Mapped[dict | None] = mapped_column(JSON)
    expected_value: Mapped[dict | None] = mapped_column(JSON)
    message: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(Text)
    result_metadata: Mapped[dict | None] = mapped_column(JSON)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    diagnostic_run: Mapped[DiagnosticRun] = relationship()


@event.listens_for(DiagnosticResult, "before_insert")
def _scope_diagnostic_result(_mapper, _connection, target: DiagnosticResult) -> None:
    """Keep legacy ORM construction compatible while enforcing result scope."""
    if target.diagnostic_run is not None:
        target.organization_id = target.organization_id or target.diagnostic_run.organization_id
        target.device_id = target.device_id or target.diagnostic_run.device_id


class RootCauseAnalysis(TimestampMixin, Base):
    __tablename__ = "root_cause_analyses"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_root_cause_analyses_id_organization"),
        UniqueConstraint(
            "id", "device_id", "organization_id",
            name="uq_root_cause_analyses_id_device_organization",
        ),
        Index("ix_root_cause_analyses_org_status", "organization_id", "status"),
        Index("ix_root_cause_analyses_run", "diagnostic_run_id"),
        ForeignKeyConstraint(
            ["device_id", "organization_id"], ["devices.id", "devices.organization_id"],
            name="fk_root_cause_analyses_device_organization",
        ),
        ForeignKeyConstraint(
            ["diagnostic_run_id", "device_id", "organization_id"],
            [
                "diagnostic_runs.id", "diagnostic_runs.device_id",
                "diagnostic_runs.organization_id",
            ],
            name="fk_root_cause_analyses_run_organization",
        ),
    )
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    diagnostic_run_id: Mapped[UUID] = mapped_column(nullable=False)
    initiated_by_user_id: Mapped = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="deterministic")
    status: Mapped[RootCauseAnalysisStatus] = mapped_column(
        Enum(RootCauseAnalysisStatus, name="root_cause_analysis_status"),
        default=RootCauseAnalysisStatus.PENDING, nullable=False, index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    organization: Mapped[Organization] = relationship(back_populates="root_cause_analyses")
    device: Mapped[Device] = relationship(overlaps="organization,root_cause_analyses")
    diagnostic_run: Mapped[DiagnosticRun] = relationship(
        overlaps="device,organization,root_cause_analyses"
    )
    findings: Mapped[list["RootCauseFinding"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class RootCauseFinding(TimestampMixin, Base):
    __tablename__ = "root_cause_findings"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_root_cause_findings_id_organization"),
        UniqueConstraint(
            "id", "device_id", "organization_id",
            name="uq_root_cause_findings_id_device_organization",
        ),
        UniqueConstraint("analysis_id", "fingerprint", name="uq_root_cause_findings_analysis_fingerprint"),
        Index("ix_root_cause_findings_analysis", "analysis_id"),
        Index("ix_root_cause_findings_org_device", "organization_id", "device_id"),
        ForeignKeyConstraint(
            ["analysis_id", "device_id", "organization_id"],
            [
                "root_cause_analyses.id", "root_cause_analyses.device_id",
                "root_cause_analyses.organization_id",
            ],
            name="fk_root_cause_findings_analysis_organization",
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id"], ["devices.id", "devices.organization_id"],
            name="fk_root_cause_findings_device_organization",
        ),
        ForeignKeyConstraint(
            ["diagnostic_result_id", "device_id", "organization_id"],
            [
                "diagnostic_results.id", "diagnostic_results.device_id",
                "diagnostic_results.organization_id",
            ],
            name="fk_root_cause_findings_result_organization",
        ),
    )
    id: Mapped = uuid_pk()
    analysis_id: Mapped[UUID] = mapped_column(nullable=False)
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    diagnostic_result_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[RootCauseFindingStatus] = mapped_column(
        Enum(RootCauseFindingStatus, name="root_cause_finding_status"), nullable=False
    )
    severity: Mapped[RootCauseFindingSeverity] = mapped_column(
        Enum(RootCauseFindingSeverity, name="root_cause_finding_severity"), nullable=False
    )
    confidence: Mapped[RootCauseFindingConfidence] = mapped_column(
        Enum(RootCauseFindingConfidence, name="root_cause_finding_confidence"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    analysis: Mapped[RootCauseAnalysis] = relationship(back_populates="findings")


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["root_cause_finding_id", "device_id", "organization_id"],
            ["root_cause_findings.id", "root_cause_findings.device_id", "root_cause_findings.organization_id"],
            name="fk_recommendations_finding_scope", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["diagnostic_result_id", "device_id", "organization_id"],
            ["diagnostic_results.id", "diagnostic_results.device_id", "diagnostic_results.organization_id"],
            name="fk_recommendations_result_scope", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["device_id", "organization_id"],
            ["devices.id", "devices.organization_id"],
            name="fk_recommendations_device_scope",
        ),
        ForeignKeyConstraint(
            ["root_cause_analysis_id", "device_id", "organization_id"],
            ["root_cause_analyses.id", "root_cause_analyses.device_id", "root_cause_analyses.organization_id"],
            name="fk_recommendations_analysis_scope",
        ),
        UniqueConstraint(
            "organization_id", "device_id", "root_cause_finding_id",
            "rule_id", "fingerprint", name="uq_recommendations_deterministic_identity",
        ),
    )
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    incident_id: Mapped = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    diagnostic_result_id: Mapped[UUID | None] = mapped_column(nullable=True)
    root_cause_finding_id: Mapped[UUID | None] = mapped_column(
        nullable=True, index=True
    )
    root_cause_analysis_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    decided_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rationale: Mapped[str | None] = mapped_column(Text)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    implemented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    implementation_notes: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="GENERAL")
    severity: Mapped[RecommendationSeverity] = mapped_column(
        Enum(RecommendationSeverity, name="recommendation_severity",
             values_callable=lambda values: [item.value for item in values]),
        nullable=False, default=RecommendationSeverity.MEDIUM,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_effect: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[RecommendationConfidence] = mapped_column(
        Enum(RecommendationConfidence, name="recommendation_confidence",
             values_callable=lambda values: [item.value for item in values]),
        nullable=False, default=RecommendationConfidence.MEDIUM,
    )
    remediation_type: Mapped[RecommendationRemediationType] = mapped_column(
        Enum(RecommendationRemediationType, name="recommendation_remediation_type",
             values_callable=lambda values: [item.value for item in values]),
        nullable=False, default=RecommendationRemediationType.GUIDANCE,
    )
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[RecommendationPriority] = mapped_column(
        Enum(RecommendationPriority, name="recommendation_priority"), default=RecommendationPriority.MEDIUM, nullable=False
    )
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, name="recommendation_status",
             values_callable=lambda values: [item.value for item in values]),
        default=RecommendationStatus.PENDING, nullable=False
    )
    organization: Mapped[Organization] = relationship(back_populates="recommendations")
    device: Mapped[Device | None] = relationship(foreign_keys=[device_id])
    incident: Mapped[Incident | None] = relationship()
    diagnostic_result: Mapped[DiagnosticResult | None] = relationship(
        foreign_keys=[diagnostic_result_id, device_id, organization_id],
        overlaps="organization,recommendations,device,root_cause_finding"
    )
    root_cause_finding: Mapped["RootCauseFinding | None"] = relationship(
        foreign_keys=[root_cause_finding_id, device_id, organization_id],
        overlaps="organization,recommendations,device,diagnostic_result"
    )


class RepairAction(TimestampMixin, Base):
    __tablename__ = "repair_actions"
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id: Mapped = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    recommendation_id: Mapped = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[RepairActionStatus] = mapped_column(
        Enum(RepairActionStatus, name="repair_action_status"), default=RepairActionStatus.REQUESTED, nullable=False
    )
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    executed_by: Mapped[str | None] = mapped_column(String(255))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[str | None] = mapped_column(String(50))
    verification_result: Mapped[dict | None] = mapped_column(JSON)
    organization: Mapped[Organization] = relationship(back_populates="repair_actions")
    device: Mapped[Device] = relationship()
    incident: Mapped[Incident | None] = relationship()
    recommendation: Mapped[Recommendation | None] = relationship()


class Escalation(TimestampMixin, Base):
    __tablename__ = "escalations"
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id: Mapped = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    escalation_level: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus, name="escalation_status"), default=EscalationStatus.OPEN, nullable=False, index=True
    )
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    escalated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organization: Mapped[Organization] = relationship(back_populates="escalations")
    incident: Mapped[Incident] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity", "resource_type", "resource_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )
    id: Mapped = uuid_pk()
    organization_id: Mapped[object | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id: Mapped[object | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    organization: Mapped[Organization | None] = relationship(back_populates="audit_events")


class BootstrapState(Base):
    __tablename__ = "bootstrap_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

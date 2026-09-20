"""SQLAlchemy domain models for the Phase 1A persistence foundation."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, uuid_pk
from .enums import (
    DeviceStatus,
    DiagnosticResultSeverity,
    DiagnosticResultStatus,
    DiagnosticRunStatus,
    EscalationStatus,
    IncidentPriority,
    IncidentSeverity,
    IncidentStatus,
    OrganizationStatus,
    RecommendationPriority,
    RecommendationStatus,
    RepairActionStatus,
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
    devices: Mapped[list["Device"]] = relationship(back_populates="organization")


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_roles_org_name"),)
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    organization: Mapped[Organization] = relationship()
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
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.ACTIVE, nullable=False, index=True
    )
    organization: Mapped[Organization] = relationship(back_populates="users")
    roles: Mapped[list[Role]] = relationship(secondary="user_roles", back_populates="users")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
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
    device: Mapped[Device | None] = relationship()
    assigned_user: Mapped[User | None] = relationship()


class DiagnosticRun(TimestampMixin, Base):
    __tablename__ = "diagnostic_runs"
    __table_args__ = (Index("ix_diagnostic_runs_status_started_at", "status", "started_at"),)
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id: Mapped = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    diagnostic_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[DiagnosticRunStatus] = mapped_column(
        Enum(DiagnosticRunStatus, name="diagnostic_run_status"), default=DiagnosticRunStatus.PENDING, nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device: Mapped[Device] = relationship()
    incident: Mapped[Incident | None] = relationship()


class DiagnosticResult(TimestampMixin, Base):
    __tablename__ = "diagnostic_results"
    id: Mapped = uuid_pk()
    diagnostic_run_id: Mapped = mapped_column(ForeignKey("diagnostic_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    check_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
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
    diagnostic_run: Mapped[DiagnosticRun] = relationship()


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"
    id: Mapped = uuid_pk()
    organization_id: Mapped = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    incident_id: Mapped = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    diagnostic_result_id: Mapped = mapped_column(ForeignKey("diagnostic_results.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[RecommendationPriority] = mapped_column(
        Enum(RecommendationPriority, name="recommendation_priority"), default=RecommendationPriority.MEDIUM, nullable=False
    )
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, name="recommendation_status"), default=RecommendationStatus.PROPOSED, nullable=False
    )
    device: Mapped[Device | None] = relationship()
    incident: Mapped[Incident | None] = relationship()
    diagnostic_result: Mapped[DiagnosticResult | None] = relationship()


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

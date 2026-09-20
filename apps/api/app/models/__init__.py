"""SQLAlchemy domain models for the Phase 1A persistence foundation."""

from .base import Base, GUID, TimestampMixin
from .domain import (
    AuditEvent, Device, DiagnosticResult, DiagnosticRun, Escalation, Incident,
    Organization, Recommendation, RepairAction, Role, User, UserRole,
)
from .enums import (
    DeviceStatus, DiagnosticResultSeverity, DiagnosticResultStatus,
    DiagnosticRunStatus, EscalationStatus, IncidentPriority, IncidentSeverity,
    IncidentStatus, OrganizationStatus, RecommendationPriority, RecommendationStatus,
    RepairActionStatus, UserStatus,
)

__all__ = [
    "Base", "GUID", "TimestampMixin", "Organization", "Role", "User", "UserRole",
    "Device", "Incident", "DiagnosticRun", "DiagnosticResult", "Recommendation",
    "RepairAction", "Escalation", "AuditEvent", "DeviceStatus", "DiagnosticRunStatus",
    "EscalationStatus", "IncidentPriority", "IncidentSeverity", "IncidentStatus",
    "OrganizationStatus", "RecommendationPriority", "RecommendationStatus",
    "RepairActionStatus", "UserStatus", "DiagnosticResultStatus",
    "DiagnosticResultSeverity",
]

"""SQLAlchemy domain models for the Phase 1A persistence foundation."""

from .base import Base, GUID, TimestampMixin
from .domain import (
    AuditEvent, BootstrapState, Device, DiagnosticResult, DiagnosticRun, DiscoveryJob, DiscoveryResult, Escalation,
    Incident, Organization, Recommendation, RepairAction, Role, User, UserRole,
    RootCauseAnalysis, RootCauseFinding, RemediationPlan, RemediationAction, RemediationVerification,
    Site, Network, Subnet, VLAN, WLAN, SSID,
)
from .enums import (
    AssetType, DeviceAssetType, DeviceCriticality, DeviceStatus, DiagnosticCheckType, DiagnosticResultSeverity,
    DiagnosticResultStatus, DiagnosticRunStatus, DiscoveryJobStatus, DiscoveryResultStatus, EscalationStatus,
    IncidentPriority, IncidentSeverity, IncidentStatus, OrganizationStatus, RecommendationConfidence,
    RecommendationPriority, RecommendationRemediationType, RecommendationSeverity, RecommendationStatus,
    ReconciliationStatus, RepairActionStatus, RootCauseAnalysisStatus, RootCauseFindingConfidence,
    RootCauseFindingSeverity, RootCauseFindingStatus, UserStatus,
    RemediationPlanStatus, RemediationActionStatus, RemediationVerificationStatus,
)

__all__ = [
    "Base", "GUID", "TimestampMixin", "Organization", "Role", "User", "UserRole",
    "Device", "Site", "Network", "Subnet", "VLAN", "WLAN", "SSID", "DiscoveryJob", "DiscoveryResult", "Incident",
    "DiagnosticRun", "DiagnosticResult", "Recommendation",
    "RepairAction", "Escalation", "AuditEvent", "BootstrapState", "DeviceStatus", "DiagnosticRunStatus",
    "EscalationStatus", "IncidentPriority", "IncidentSeverity", "IncidentStatus",
    "OrganizationStatus", "AssetType", "DeviceAssetType", "DeviceCriticality", "RecommendationPriority", "RecommendationStatus",
    "RecommendationSeverity", "RecommendationConfidence", "RecommendationRemediationType",
    "RepairActionStatus", "UserStatus", "DiagnosticResultStatus",
    "DiagnosticResultSeverity", "DiscoveryJobStatus", "DiscoveryResultStatus", "ReconciliationStatus",
    "DiagnosticCheckType",
    "RootCauseAnalysis", "RootCauseFinding", "RootCauseAnalysisStatus", "RootCauseFindingSeverity",
    "RootCauseFindingStatus", "RootCauseFindingConfidence",
    "RemediationPlan", "RemediationAction", "RemediationVerification",
    "RemediationPlanStatus", "RemediationActionStatus", "RemediationVerificationStatus",
]

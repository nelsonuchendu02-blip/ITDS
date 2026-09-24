"""Pydantic schemas for API boundaries."""

from .device import DeviceCreate, DeviceRead
from .device_management import (
    DeviceManagementCreate,
    DeviceManagementRead,
    DeviceManagementUpdate,
    DevicePage,
    DevicePageMeta,
)
from .discovery import (
    DiscoveryJobCreate,
    DiscoveryJobPage,
    DiscoveryJobRead,
    DiscoveryPageMeta,
    DiscoveryResultPage,
    DiscoveryResultRead,
)
from .diagnostics import (
    DiagnosticPageMeta, DiagnosticResultPage, DiagnosticResultRead, DiagnosticRunCreate,
    DiagnosticRunPage, DiagnosticRunRead,
)
from .organization import OrganizationCreate, OrganizationRead
from .auth import TokenRequest, TokenResponse
from .user import CurrentUserRead, UserRead
from .management import (
    AuditEventPage,
    AuditEventRead,
    OrganizationAdminRead,
    OrganizationUpdate,
    PageMeta,
    RoleAssignment,
    RoleRead,
    UserAdminRead,
    UserCreateAdmin,
    UserPage,
    UserUpdateAdmin,
)
from .root_cause import (
    RootCauseAnalysisCreate, RootCauseAnalysisPage, RootCauseAnalysisRead,
    RootCauseFindingPage, RootCauseFindingRead, RootCausePageMeta,
)
from .recommendation import RecommendationCreate, RecommendationGenerate, RecommendationPage, RecommendationPageMeta, RecommendationRead
from .remediation import RemediationGenerate, RemediationActionRead, RemediationVerificationRead, RemediationPlanRead
from .incident import (
    IncidentCreate, IncidentUpdate, IncidentAssignment, IncidentResolution,
    IncidentRead, IncidentPage, EscalationCreate, EscalationRead,
)
from .inventory import (
    AssetCreate, AssetRead, AssetUpdate, NetworkCreate, NetworkRead, NetworkUpdate,
    SiteCreate, SiteRead, SiteUpdate, SSIDCreate, SSIDRead, SSIDUpdate,
    SubnetCreate, SubnetRead, SubnetUpdate, VLANCreate, VLANRead, VLANUpdate,
)
from .monitoring import (
    MonitoringTargetCreate, MonitoringTargetRead, MonitoringTargetUpdate, MonitoringTargetPage,
    TelemetryCreate, TelemetryRead, TelemetryPage, MonitoringSummary, MonitoringPageMeta,
)
from .agent import (
    AgentEnroll, AgentEnrollmentResponse, AgentHeartbeat, AgentRead, AgentRotateResponse,
    AgentUpdate, EnrollmentTokenCreate, EnrollmentTokenRead,
)

__all__ = [
    "CurrentUserRead",
    "DeviceCreate",
    "DeviceRead",
    "DeviceManagementCreate",
    "DeviceManagementRead",
    "DeviceManagementUpdate",
    "DevicePage",
    "DevicePageMeta",
    "DiscoveryJobCreate",
    "DiscoveryJobPage",
    "DiscoveryJobRead",
    "DiscoveryPageMeta",
    "DiscoveryResultPage",
    "DiscoveryResultRead",
    "DiagnosticPageMeta", "DiagnosticResultPage", "DiagnosticResultRead",
    "DiagnosticRunCreate", "DiagnosticRunPage", "DiagnosticRunRead",
    "OrganizationCreate",
    "OrganizationRead",
    "TokenRequest",
    "TokenResponse",
    "UserRead",
    "AuditEventPage",
    "AuditEventRead",
    "OrganizationAdminRead",
    "OrganizationUpdate",
    "PageMeta",
    "RoleAssignment",
    "RoleRead",
    "UserAdminRead",
    "UserCreateAdmin",
    "UserPage",
    "RootCauseAnalysisCreate", "RootCauseAnalysisPage", "RootCauseAnalysisRead",
    "RootCauseFindingPage", "RootCauseFindingRead", "RootCausePageMeta",
    "UserUpdateAdmin",
    "RecommendationCreate", "RecommendationRead", "RecommendationPage", "RecommendationPageMeta",
    "RecommendationGenerate",
    "RemediationGenerate", "RemediationActionRead", "RemediationVerificationRead", "RemediationPlanRead",
    "IncidentCreate", "IncidentUpdate", "IncidentAssignment", "IncidentResolution",
    "IncidentRead", "IncidentPage", "EscalationCreate", "EscalationRead",
    "AssetCreate", "AssetRead", "AssetUpdate",
    "SiteCreate", "SiteRead", "SiteUpdate",
    "NetworkCreate", "NetworkRead", "NetworkUpdate",
    "SubnetCreate", "SubnetRead", "SubnetUpdate",
    "VLANCreate", "VLANRead", "VLANUpdate",
    "SSIDCreate", "SSIDRead", "SSIDUpdate",
    "MonitoringTargetCreate", "MonitoringTargetRead", "MonitoringTargetUpdate", "MonitoringTargetPage",
    "TelemetryCreate", "TelemetryRead", "TelemetryPage", "MonitoringSummary", "MonitoringPageMeta",
    "AgentEnroll", "AgentHeartbeat", "AgentRead", "AgentEnrollmentResponse", "AgentRotateResponse",
    "AgentUpdate", "EnrollmentTokenCreate", "EnrollmentTokenRead",
]

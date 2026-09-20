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
    "UserUpdateAdmin",
]

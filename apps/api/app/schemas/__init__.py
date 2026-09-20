"""Pydantic schemas for API boundaries."""

from .device import DeviceCreate, DeviceRead
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

"""Database repositories for application persistence operations."""

from .device import DeviceRepository
from .organization import OrganizationRepository

__all__ = ["DeviceRepository", "OrganizationRepository"]

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Device


class DeviceRepository:
    """Persistence operations for devices with explicit organization scoping."""

    def create(self, session: Session, device: Device) -> Device:
        session.add(device)
        session.flush()
        return device

    def get_by_id(
        self,
        session: Session,
        device_id: UUID,
        organization_id: UUID,
    ) -> Device | None:
        statement = select(Device).where(
            Device.id == device_id,
            Device.organization_id == organization_id,
        )
        return session.scalars(statement).first()

    def list_by_organization(self, session: Session, organization_id: UUID) -> Sequence[Device]:
        statement = select(Device).where(Device.organization_id == organization_id).order_by(Device.hostname)
        return session.scalars(statement).all()

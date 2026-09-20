from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Device, DeviceStatus


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

    def list_page(
        self,
        session: Session,
        organization_id: UUID,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        status: DeviceStatus | None = None,
        device_type: str | None = None,
        operating_system: str | None = None,
    ) -> tuple[list[Device], int]:
        filters = [Device.organization_id == organization_id]
        if search:
            pattern = f"%{search.strip().lower()}%"
            filters.append(
                func.lower(Device.hostname).like(pattern)
                | func.lower(Device.device_type).like(pattern)
                | func.lower(Device.operating_system).like(pattern)
            )
        if status:
            filters.append(Device.status == status)
        if device_type:
            filters.append(Device.device_type == device_type)
        if operating_system:
            filters.append(Device.operating_system == operating_system)
        statement = select(Device).where(*filters)
        count_statement = select(func.count()).select_from(Device).where(*filters)
        total = session.scalar(count_statement) or 0
        devices = session.scalars(
            statement.order_by(Device.hostname, Device.id).offset(offset).limit(limit)
        ).all()
        return devices, total

    def update(self, device: Device, *, hostname: str, device_type: str, operating_system: str,
               ip_address: str | None) -> Device:
        device.hostname = hostname
        device.device_type = device_type
        device.operating_system = operating_system
        device.ip_address = ip_address
        return device

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import PersistenceError
from ..models import Device
from ..repositories import DeviceRepository


class DeviceService:
    """Coordinate device persistence while requiring organization scope."""

    def __init__(self, repository: DeviceRepository | None = None) -> None:
        self.repository = repository or DeviceRepository()

    def create_device(
        self,
        session: Session,
        *,
        organization_id: UUID,
        hostname: str,
        device_type: str,
        operating_system: str,
        ip_address: str | None = None,
    ) -> Device:
        device = Device(
            organization_id=organization_id,
            hostname=hostname,
            device_type=device_type,
            operating_system=operating_system,
            ip_address=ip_address,
        )
        try:
            device = self.repository.create(session, device)
            session.commit()
            return device
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Device could not be created") from exc

    def get_device(
        self,
        session: Session,
        device_id: UUID,
        *,
        organization_id: UUID,
    ) -> Device | None:
        return self.repository.get_by_id(session, device_id, organization_id)

    def list_devices(self, session: Session, *, organization_id: UUID) -> Sequence[Device]:
        return self.repository.list_by_organization(session, organization_id)

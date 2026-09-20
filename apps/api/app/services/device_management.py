from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import PersistenceError, SecurityError
from ..models import Device, DeviceStatus, User
from ..repositories import DeviceRepository
from .audit import record_security_event


class DeviceManagementService:
    def __init__(self, repository: DeviceRepository | None = None) -> None:
        self.repository = repository or DeviceRepository()

    def create_device(
        self, session: Session, *, organization_id: UUID, actor: User,
        hostname: str, device_type: str, operating_system: str, ip_address: str | None,
    ) -> Device:
        if actor.organization_id != organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
        device = Device(
            organization_id=organization_id,
            hostname=hostname,
            device_type=device_type,
            operating_system=operating_system,
            ip_address=ip_address,
        )
        try:
            self.repository.create(session, device)
            record_security_event(
                session, event_type="device_created", organization_id=organization_id,
                actor_user_id=actor.id, action="create", result="success",
                metadata={"target_device_id": str(device.id)}, resource_type="device",
                resource_id=str(device.id),
            )
            self._commit(session)
            return device
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Device could not be created") from exc

    def get_device(self, session: Session, device_id: UUID, organization_id: UUID) -> Device | None:
        return self.repository.get_by_id(session, device_id, organization_id)

    def list_devices(
        self, session: Session, organization_id: UUID, *, offset: int, limit: int,
        search: str | None = None, status: DeviceStatus | None = None,
        device_type: str | None = None, operating_system: str | None = None,
    ) -> tuple[list[Device], int]:
        return self.repository.list_page(
            session, organization_id, offset=offset, limit=limit, search=search,
            status=status, device_type=device_type,
            operating_system=operating_system,
        )

    def update_device(
        self, session: Session, *, device: Device, actor: User,
        hostname: str, device_type: str, operating_system: str, ip_address: str | None,
    ) -> Device:
        if device.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
        self.repository.update(
            device, hostname=hostname, device_type=device_type,
            operating_system=operating_system, ip_address=ip_address,
        )
        record_security_event(
            session, event_type="device_updated", organization_id=device.organization_id,
            actor_user_id=actor.id, action="update", result="success",
            metadata={"target_device_id": str(device.id)}, resource_type="device",
            resource_id=str(device.id),
        )
        self._commit(session)
        return device

    def set_status(
        self, session: Session, *, device: Device, actor: User, status: DeviceStatus
    ) -> Device:
        if device.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
        device.status = status
        record_security_event(
            session,
            event_type="device_activated" if status is DeviceStatus.ACTIVE else "device_deactivated",
            organization_id=device.organization_id,
            actor_user_id=actor.id,
            action="status_change",
            result="success",
            metadata={"target_device_id": str(device.id), "status": status.value},
            resource_type="device",
            resource_id=str(device.id),
        )
        self._commit(session)
        return device

    @staticmethod
    def _commit(session: Session) -> None:
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Device operation could not be completed") from exc

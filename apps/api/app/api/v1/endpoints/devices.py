from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...dependencies.auth import get_device_management_service, require_permission
from ....db import get_db
from ....exceptions import SecurityError
from ....models import Device, DeviceStatus, User
from ....schemas import (
    DeviceManagementCreate,
    DeviceManagementRead,
    DeviceManagementUpdate,
    DevicePage,
    DevicePageMeta,
)
from ....services import DeviceManagementService

router = APIRouter(prefix="/devices", tags=["devices"])
Service = Annotated[DeviceManagementService, Depends(get_device_management_service)]


def _not_found() -> SecurityError:
    return SecurityError("device_not_found", "Device not found", 404)


@router.get("", response_model=DevicePage)
def list_devices(
    user: Annotated[User, Depends(require_permission("devices:read"))],
    service: Service,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    status: DeviceStatus | None = None,
    device_type: str | None = Query(default=None, min_length=1, max_length=100),
    operating_system: str | None = Query(default=None, min_length=1, max_length=200),
) -> DevicePage:
    items, total = service.list_devices(
        session,
        user.organization_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        search=search,
        status=status,
        device_type=device_type,
        operating_system=operating_system,
    )
    return DevicePage(
        items=items,
        meta=DevicePageMeta(page=page, page_size=page_size, total=total),
    )


@router.post("", response_model=DeviceManagementRead, status_code=201)
def create_device(
    payload: DeviceManagementCreate,
    user: Annotated[User, Depends(require_permission("devices:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> Device:
    return service.create_device(
        session,
        organization_id=user.organization_id,
        actor=user,
        hostname=payload.hostname,
        device_type=payload.device_type,
        operating_system=payload.operating_system,
        ip_address=payload.ip_address,
    )


@router.get("/{device_id}", response_model=DeviceManagementRead)
def get_device(
    device_id: UUID,
    user: Annotated[User, Depends(require_permission("devices:read"))],
    service: Service,
    session: Session = Depends(get_db),
) -> Device:
    device = service.get_device(session, device_id, user.organization_id)
    if device is None:
        raise _not_found()
    return device


@router.patch("/{device_id}", response_model=DeviceManagementRead)
def update_device(
    device_id: UUID,
    payload: DeviceManagementUpdate,
    user: Annotated[User, Depends(require_permission("devices:write"))],
    service: Service,
    session: Session = Depends(get_db),
) -> Device:
    device = service.get_device(session, device_id, user.organization_id)
    if device is None:
        raise _not_found()
    values = payload.model_dump(exclude_unset=True)
    return service.update_device(
        session,
        device=device,
        actor=user,
        hostname=values.get("hostname", device.hostname),
        device_type=values.get("device_type", device.device_type),
        operating_system=values.get("operating_system", device.operating_system),
        ip_address=values.get("ip_address", device.ip_address),
    )


def _set_device_status(
    device_id: UUID,
    status: DeviceStatus,
    user: User,
    service: DeviceManagementService,
    session: Session,
) -> Device:
    device = service.get_device(session, device_id, user.organization_id)
    if device is None:
        raise _not_found()
    return service.set_status(session, device=device, actor=user, status=status)


@router.post("/{device_id}/activate", response_model=DeviceManagementRead)
def activate_device(
    device_id: UUID,
    user: Annotated[User, Depends(require_permission("devices:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> Device:
    return _set_device_status(device_id, DeviceStatus.ACTIVE, user, service, session)


@router.post("/{device_id}/deactivate", response_model=DeviceManagementRead)
def deactivate_device(
    device_id: UUID,
    user: Annotated[User, Depends(require_permission("devices:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> Device:
    return _set_device_status(device_id, DeviceStatus.INACTIVE, user, service, session)

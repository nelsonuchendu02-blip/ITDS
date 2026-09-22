from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ....db import get_db
from ....models import User
from ....schemas import (
    MonitoringPageMeta, MonitoringSummary, MonitoringTargetCreate, MonitoringTargetPage,
    MonitoringTargetRead, MonitoringTargetUpdate, TelemetryCreate, TelemetryPage, TelemetryRead,
)
from ....models import HealthStatus
from ....services.monitoring import MonitoringService
from ...dependencies.auth import get_monitoring_service, require_permission

router = APIRouter(prefix="/monitoring", tags=["monitoring"])
Service = Annotated[MonitoringService, Depends(get_monitoring_service)]


def _target(service, session, user, target_id):
    target = service.repository.target(session, user.organization_id, target_id)
    if target is None:
        from ....exceptions import SecurityError
        raise SecurityError("monitoring_target_not_found", "Monitoring target not found", 404)
    return target


@router.post("/targets", response_model=MonitoringTargetRead, status_code=201)
def create_target(payload: MonitoringTargetCreate,
                  user: Annotated[User, Depends(require_permission("monitoring:create"))],
                  service: Service, session: Session = Depends(get_db)):
    return service.target_read(service.create_target(session, user, payload.model_dump()))


@router.get("/targets", response_model=MonitoringTargetPage)
def list_targets(user: Annotated[User, Depends(require_permission("monitoring:read"))],
                 service: Service, session: Session = Depends(get_db),
                 page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                 enabled: bool | None = None, health_status: HealthStatus | None = None,
                 device_id: UUID | None = None):
    items, total = service.target_page(session, user.organization_id, (page - 1) * page_size, page_size,
                                       enabled=enabled, health_status=health_status, device_id=device_id)
    return MonitoringTargetPage(items=items, meta=MonitoringPageMeta(page=page, page_size=page_size, total=total))


@router.get("/targets/{target_id}", response_model=MonitoringTargetRead)
def get_target(target_id: UUID, user: Annotated[User, Depends(require_permission("monitoring:read"))],
               service: Service, session: Session = Depends(get_db)):
    return service.target_read(_target(service, session, user, target_id))


@router.patch("/targets/{target_id}", response_model=MonitoringTargetRead)
def update_target(target_id: UUID, payload: MonitoringTargetUpdate,
                  user: Annotated[User, Depends(require_permission("monitoring:manage"))],
                  service: Service, session: Session = Depends(get_db)):
    target = service.update_target(session, _target(service, session, user, target_id),
                                   user, payload.model_dump(exclude_unset=True))
    return service.target_read(target)


@router.post("/targets/{target_id}/enable", response_model=MonitoringTargetRead)
def enable_target(target_id: UUID, user: Annotated[User, Depends(require_permission("monitoring:manage"))],
                  service: Service, session: Session = Depends(get_db)):
    target = service.set_enabled(session, _target(service, session, user, target_id), user, True)
    return service.target_read(target)


@router.post("/targets/{target_id}/disable", response_model=MonitoringTargetRead)
def disable_target(target_id: UUID, user: Annotated[User, Depends(require_permission("monitoring:manage"))],
                   service: Service, session: Session = Depends(get_db)):
    target = service.set_enabled(session, _target(service, session, user, target_id), user, False)
    return service.target_read(target)


@router.post("/targets/{target_id}/telemetry", response_model=TelemetryRead, status_code=201)
def ingest_telemetry(target_id: UUID, payload: TelemetryCreate,
                     user: Annotated[User, Depends(require_permission("monitoring:ingest"))],
                     service: Service, session: Session = Depends(get_db)):
    return service.ingest(session, _target(service, session, user, target_id), user, payload.model_dump())


@router.get("/targets/{target_id}/telemetry", response_model=TelemetryPage)
def list_telemetry(target_id: UUID, user: Annotated[User, Depends(require_permission("monitoring:read"))],
                   service: Service, session: Session = Depends(get_db),
                   page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100)):
    _target(service, session, user, target_id)
    items, total = service.repository.telemetry(
        session, user.organization_id, target_id, (page - 1) * page_size, page_size)
    return TelemetryPage(items=items, meta=MonitoringPageMeta(page=page, page_size=page_size, total=total))


@router.get("/summary", response_model=MonitoringSummary)
def monitoring_summary(user: Annotated[User, Depends(require_permission("monitoring:read"))],
                       service: Service, session: Session = Depends(get_db)):
    return service.summary(session, user.organization_id)

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...dependencies.auth import get_discovery_service, require_permission
from ....db import get_db
from ....exceptions import SecurityError
from ....models import DiscoveryJobStatus, DiscoveryResultStatus, ReconciliationStatus, User
from ....schemas import (
    DiscoveryJobCreate,
    DiscoveryJobPage,
    DiscoveryJobRead,
    DiscoveryPageMeta,
    DiscoveryResultPage,
    DiscoveryResultRead,
)
from ....services import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["discovery"])
Service = Annotated[DiscoveryService, Depends(get_discovery_service)]


def _not_found() -> SecurityError:
    return SecurityError("discovery_job_not_found", "Discovery job not found", 404)


@router.post("/jobs", response_model=DiscoveryJobRead, status_code=201)
def create_job(
    payload: DiscoveryJobCreate,
    user: Annotated[User, Depends(require_permission("discovery:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> DiscoveryJobRead:
    return service.create_job(
        session, organization_id=user.organization_id, actor=user,
        provider=payload.provider, target=payload.target,
    )


@router.get("/jobs", response_model=DiscoveryJobPage)
def list_jobs(
    user: Annotated[User, Depends(require_permission("discovery:read"))],
    service: Service,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    status: DiscoveryJobStatus | None = None,
    provider: str | None = Query(default=None, min_length=1, max_length=50),
) -> DiscoveryJobPage:
    items, total = service.list_jobs(
        session, user.organization_id, offset=(page - 1) * page_size,
        limit=page_size, status=status, provider=provider,
    )
    return DiscoveryJobPage(
        items=items,
        meta=DiscoveryPageMeta(page=page, page_size=page_size, total=total),
    )


@router.get("/jobs/{job_id}", response_model=DiscoveryJobRead)
def get_job(
    job_id: UUID,
    user: Annotated[User, Depends(require_permission("discovery:read"))],
    service: Service,
    session: Session = Depends(get_db),
) -> DiscoveryJobRead:
    job = service.get_job(session, job_id, user.organization_id)
    if job is None:
        raise _not_found()
    return job


@router.post("/jobs/{job_id}/run", response_model=DiscoveryJobRead)
def run_job(
    job_id: UUID,
    user: Annotated[User, Depends(require_permission("discovery:run"))],
    service: Service,
    session: Session = Depends(get_db),
) -> DiscoveryJobRead:
    job = service.get_job(session, job_id, user.organization_id)
    if job is None:
        raise _not_found()
    return service.start_job(session, job=job, actor=user)


@router.post("/jobs/{job_id}/cancel", response_model=DiscoveryJobRead)
def cancel_job(
    job_id: UUID,
    user: Annotated[User, Depends(require_permission("discovery:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> DiscoveryJobRead:
    job = service.get_job(session, job_id, user.organization_id)
    if job is None:
        raise _not_found()
    return service.cancel_job(session, job=job, actor=user)


@router.get("/jobs/{job_id}/results", response_model=DiscoveryResultPage)
def list_results(
    job_id: UUID,
    user: Annotated[User, Depends(require_permission("discovery:read"))],
    service: Service,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    status: DiscoveryResultStatus | None = None,
    reconciliation_status: ReconciliationStatus | None = None,
    ip: str | None = Query(default=None, min_length=1, max_length=45),
    hostname: str | None = Query(default=None, min_length=1, max_length=255),
) -> DiscoveryResultPage:
    job = service.get_job(session, job_id, user.organization_id)
    if job is None:
        raise _not_found()
    items, total = service.list_results(
        session, job=job, organization_id=user.organization_id,
        offset=(page - 1) * page_size, limit=page_size,
        status=status, reconciliation_status=reconciliation_status,
        ip=ip, hostname=hostname,
    )
    return DiscoveryResultPage(
        items=items,
        meta=DiscoveryPageMeta(page=page, page_size=page_size, total=total),
    )

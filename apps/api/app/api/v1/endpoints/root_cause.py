from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...dependencies.auth import get_root_cause_service, require_permission
from ....db import get_db
from ....exceptions import SecurityError
from ....models import User
from ....schemas import (
    RootCauseAnalysisCreate, RootCauseAnalysisPage, RootCauseAnalysisRead,
    RootCauseFindingPage, RootCausePageMeta,
)
from ....services.root_cause import RootCauseService

router = APIRouter(prefix="/root-cause", tags=["root-cause"])
Service = Annotated[RootCauseService, Depends(get_root_cause_service)]


def _missing() -> SecurityError:
    return SecurityError("root_cause_analysis_not_found", "Root-cause analysis not found", 404)


@router.post("/analyses", response_model=RootCauseAnalysisRead, status_code=201)
def create_analysis(payload: RootCauseAnalysisCreate,
                    user: Annotated[User, Depends(require_permission("root_cause:run"))],
                    service: Service, session: Session = Depends(get_db)):
    return service.create(session, organization_id=user.organization_id,
                          diagnostic_run_id=payload.diagnostic_run_id, actor=user)


@router.get("/analyses", response_model=RootCauseAnalysisPage)
def list_analyses(user: Annotated[User, Depends(require_permission("root_cause:read"))],
                  service: Service, session: Session = Depends(get_db),
                  page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100)):
    items, total = service.list(session, user.organization_id,
                                 offset=(page - 1) * page_size, limit=page_size)
    return RootCauseAnalysisPage(items=items, meta=RootCausePageMeta(
        page=page, page_size=page_size, total=total))


@router.get("/analyses/{analysis_id}", response_model=RootCauseAnalysisRead)
def get_analysis(analysis_id: UUID, user: Annotated[User, Depends(require_permission("root_cause:read"))],
                 service: Service, session: Session = Depends(get_db)):
    analysis = service.get(session, analysis_id, user.organization_id)
    if analysis is None:
        raise _missing()
    return analysis


@router.post("/analyses/{analysis_id}/run", response_model=RootCauseAnalysisRead)
def run_analysis(analysis_id: UUID, user: Annotated[User, Depends(require_permission("root_cause:run"))],
                 service: Service, session: Session = Depends(get_db)):
    analysis = service.get(session, analysis_id, user.organization_id)
    if analysis is None:
        raise _missing()
    return service.run(session, analysis=analysis, actor=user)


@router.post("/analyses/{analysis_id}/cancel", response_model=RootCauseAnalysisRead)
def cancel_analysis(analysis_id: UUID, user: Annotated[User, Depends(require_permission("root_cause:manage"))],
                    service: Service, session: Session = Depends(get_db)):
    analysis = service.get(session, analysis_id, user.organization_id)
    if analysis is None:
        raise _missing()
    return service.cancel(session, analysis=analysis, actor=user)


@router.get("/analyses/{analysis_id}/findings", response_model=RootCauseFindingPage)
def list_findings(analysis_id: UUID, user: Annotated[User, Depends(require_permission("root_cause:read"))],
                  service: Service, session: Session = Depends(get_db),
                  page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100)):
    analysis = service.get(session, analysis_id, user.organization_id)
    if analysis is None:
        raise _missing()
    items = list(service.findings(session, analysis, user.organization_id))
    start = (page - 1) * page_size
    return RootCauseFindingPage(items=items[start:start + page_size],
                                meta=RootCausePageMeta(page=page, page_size=page_size, total=len(items)))

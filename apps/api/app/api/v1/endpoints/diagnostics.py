from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...dependencies.auth import get_diagnostic_service, require_permission
from ....db import get_db
from ....exceptions import SecurityError
from ....models import DiagnosticCheckType, DiagnosticRunStatus, User
from ....schemas import (
    DiagnosticPageMeta, DiagnosticResultPage, DiagnosticRunCreate, DiagnosticRunPage, DiagnosticRunRead,
)
from ....services.diagnostics import DiagnosticService

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])
Service = Annotated[DiagnosticService, Depends(get_diagnostic_service)]


@router.get("/check-types")
def check_types(user: Annotated[User, Depends(require_permission("diagnostics:read"))]):
    return {"items": [{"value": check.value, "label": check.value.replace("_", " ").title()}
                      for check in DiagnosticCheckType]}


def _missing():
    return SecurityError("diagnostic_run_not_found", "Diagnostic run not found", 404)


@router.post("/runs", response_model=DiagnosticRunRead, status_code=201)
def create_run(payload: DiagnosticRunCreate,
               user: Annotated[User, Depends(require_permission("diagnostics:run"))],
               service: Service, session: Session = Depends(get_db)):
    return service.create(session, organization_id=user.organization_id, actor=user,
                          device_id=payload.device_id, diagnostic_type=payload.diagnostic_type.value,
                          provider=payload.provider)


@router.get("/runs", response_model=DiagnosticRunPage)
def list_runs(user: Annotated[User, Depends(require_permission("diagnostics:read"))],
              service: Service, session: Session = Depends(get_db),
              page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
              status: DiagnosticRunStatus | None = None):
    items, total = service.list(session, user.organization_id,
                                 offset=(page - 1) * page_size, limit=page_size, status=status)
    return DiagnosticRunPage(items=items, meta=DiagnosticPageMeta(page=page, page_size=page_size, total=total))


@router.get("/runs/{run_id}", response_model=DiagnosticRunRead)
def get_run(run_id: UUID, user: Annotated[User, Depends(require_permission("diagnostics:read"))],
            service: Service, session: Session = Depends(get_db)):
    run = service.get(session, run_id, user.organization_id)
    if run is None:
        raise _missing()
    return run


@router.post("/runs/{run_id}/run", response_model=DiagnosticRunRead)
def run_run(run_id: UUID, user: Annotated[User, Depends(require_permission("diagnostics:run"))],
            service: Service, session: Session = Depends(get_db)):
    run = service.get(session, run_id, user.organization_id)
    if run is None:
        raise _missing()
    return service.run(session, run=run, actor=user)


@router.post("/runs/{run_id}/cancel", response_model=DiagnosticRunRead)
def cancel_run(run_id: UUID, user: Annotated[User, Depends(require_permission("diagnostics:manage"))],
               service: Service, session: Session = Depends(get_db)):
    run = service.get(session, run_id, user.organization_id)
    if run is None:
        raise _missing()
    return service.cancel(session, run=run, actor=user)


@router.get("/runs/{run_id}/results", response_model=DiagnosticResultPage)
def list_results(run_id: UUID, user: Annotated[User, Depends(require_permission("diagnostics:read"))],
                 service: Service, session: Session = Depends(get_db),
                 page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100)):
    run = service.get(session, run_id, user.organization_id)
    if run is None:
        raise _missing()
    results = list(service.results(session, run, user.organization_id))
    start = (page - 1) * page_size
    return DiagnosticResultPage(items=results[start:start + page_size],
                                meta=DiagnosticPageMeta(page=page, page_size=page_size, total=len(results)))

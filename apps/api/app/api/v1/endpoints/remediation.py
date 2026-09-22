from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...dependencies.auth import require_permission
from ....db import get_db
from ....exceptions import SecurityError
from ....models import RemediationPlanStatus, User
from ....schemas.remediation import RemediationGenerate, RemediationPlanList, RemediationPlanRead, RemediationActionRead, RemediationVerificationRead
from ....services.remediation import RemediationService

router = APIRouter(prefix="/remediation", tags=["remediation"])


def _service() -> RemediationService:
    return RemediationService()


def _plan(service, session, plan_id, user):
    plan = service.get(session, plan_id, user.organization_id)
    if plan is None:
        raise SecurityError("remediation_not_found", "Remediation plan not found", 404)
    return plan


@router.get("/plans", response_model=RemediationPlanList)
def list_plans(user: Annotated[User, Depends(require_permission("remediation:read"))],
               session: Session = Depends(get_db), limit: int = Query(100, ge=1, le=100),
               offset: int = Query(0, ge=0)):
    items = _service().list(session, user.organization_id, limit=limit, offset=offset)
    return {"items": items, "total": len(items)}


@router.post("/plans", response_model=RemediationPlanRead, status_code=201)
@router.post("/plans/generate", response_model=RemediationPlanRead, status_code=201)
def generate_plan(payload: RemediationGenerate,
                  user: Annotated[User, Depends(require_permission("remediation:create"))],
                  session: Session = Depends(get_db)):
    return _service().generate(session, payload.recommendation_id, user)


@router.get("/plans/{plan_id}", response_model=RemediationPlanRead)
def get_plan(plan_id: UUID, user: Annotated[User, Depends(require_permission("remediation:read"))],
             session: Session = Depends(get_db)):
    return _plan(_service(), session, plan_id, user)


@router.get("/plans/{plan_id}/actions", response_model=list[RemediationActionRead])
def list_actions(plan_id: UUID, user: Annotated[User, Depends(require_permission("remediation:read"))],
                 session: Session = Depends(get_db)):
    plan = _plan(_service(), session, plan_id, user)
    return plan.actions


@router.get("/plans/{plan_id}/verification-results", response_model=list[RemediationVerificationRead])
def verification_results(plan_id: UUID, user: Annotated[User, Depends(require_permission("remediation:read"))],
                         session: Session = Depends(get_db)):
    plan = _plan(_service(), session, plan_id, user)
    return plan.verifications


def _transition(target: RemediationPlanStatus, permission: str):
    def handler(plan_id: UUID, user: Annotated[User, Depends(require_permission(permission))],
                session: Session = Depends(get_db)):
        service = _service()
        return service.transition(session, _plan(service, session, plan_id, user), user, target)
    return handler


router.post("/plans/{plan_id}/submit", response_model=RemediationPlanRead)(
    _transition(RemediationPlanStatus.PENDING_APPROVAL, "remediation:create"))
router.post("/plans/{plan_id}/approve", response_model=RemediationPlanRead)(
    _transition(RemediationPlanStatus.APPROVED, "remediation:approve"))
router.post("/plans/{plan_id}/reject", response_model=RemediationPlanRead)(
    _transition(RemediationPlanStatus.REJECTED, "remediation:approve"))
router.post("/plans/{plan_id}/queue", response_model=RemediationPlanRead)(
    _transition(RemediationPlanStatus.QUEUED, "remediation:manage"))
router.post("/plans/{plan_id}/cancel", response_model=RemediationPlanRead)(
    _transition(RemediationPlanStatus.CANCELLED, "remediation:manage"))


@router.post("/plans/{plan_id}/execute", response_model=RemediationPlanRead)
def execute_plan(plan_id: UUID, user: Annotated[User, Depends(require_permission("remediation:execute"))],
                 session: Session = Depends(get_db)):
    service = _service()
    return service.execute(session, _plan(service, session, plan_id, user), user)


@router.post("/plans/{plan_id}/verify", response_model=RemediationPlanRead)
def verify_plan(plan_id: UUID, user: Annotated[User, Depends(require_permission("remediation:verify"))],
                session: Session = Depends(get_db)):
    service = _service()
    return service.verify(session, _plan(service, session, plan_id, user), user)

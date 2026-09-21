from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...dependencies.auth import get_recommendation_service, require_permission
from ....db import get_db
from ....exceptions import SecurityError
from ....models import RecommendationStatus, User
from ....schemas import RecommendationCreate, RecommendationGenerate, RecommendationPage, RecommendationPageMeta, RecommendationRead
from ....services.recommendation import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
Service = Annotated[RecommendationService, Depends(get_recommendation_service)]


def _missing() -> SecurityError:
    return SecurityError("recommendation_not_found", "Recommendation not found", 404)


@router.post("", response_model=RecommendationRead, status_code=201)
def create_recommendation(
    payload: RecommendationCreate,
    user: Annotated[User, Depends(require_permission("recommendations:run"))],
    service: Service,
    session: Session = Depends(get_db),
):
    return service.create(session, organization_id=user.organization_id, actor=user,
                          finding_id=payload.root_cause_finding_id)


@router.post("/generate", response_model=list[RecommendationRead], status_code=201)
def generate_recommendations(
    payload: RecommendationGenerate,
    user: Annotated[User, Depends(require_permission("recommendations:run"))],
    service: Service,
    session: Session = Depends(get_db),
):
    return service.generate(session, organization_id=user.organization_id, actor=user,
                            analysis_id=payload.analysis_id)


@router.get("", response_model=RecommendationPage)
def list_recommendations(
    user: Annotated[User, Depends(require_permission("recommendations:read"))],
    service: Service,
    session: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: RecommendationStatus | None = None,
):
    items, total = service.list(session, user.organization_id, offset=(page - 1) * page_size,
                                limit=page_size, status=status)
    return RecommendationPage(items=items, meta=RecommendationPageMeta(
        page=page, page_size=page_size, total=total))


@router.get("/{recommendation_id}", response_model=RecommendationRead)
def get_recommendation(
    recommendation_id: UUID,
    user: Annotated[User, Depends(require_permission("recommendations:read"))],
    service: Service,
    session: Session = Depends(get_db),
):
    recommendation = service.get(session, recommendation_id, user.organization_id)
    if recommendation is None:
        raise _missing()
    return recommendation


def _transition(target: RecommendationStatus):
    def handler(
        recommendation_id: UUID,
        user: Annotated[User, Depends(require_permission("recommendations:manage"))],
        service: Service,
        session: Session = Depends(get_db),
    ):
        recommendation = service.get(session, recommendation_id, user.organization_id)
        if recommendation is None:
            raise _missing()
        return service.transition(session, recommendation=recommendation, actor=user, target=target)
    return handler


router.post("/{recommendation_id}/review", response_model=RecommendationRead)(
    _transition(RecommendationStatus.REVIEWED)
)
router.post("/{recommendation_id}/reject", response_model=RecommendationRead)(
    _transition(RecommendationStatus.REJECTED)
)
router.post("/{recommendation_id}/accept", response_model=RecommendationRead)(
    _transition(RecommendationStatus.ACCEPTED)
)
router.post("/{recommendation_id}/implement", response_model=RecommendationRead)(
    _transition(RecommendationStatus.IMPLEMENTED)
)

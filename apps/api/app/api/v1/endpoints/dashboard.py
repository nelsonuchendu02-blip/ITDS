from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....db import get_db
from ....models import User
from ....schemas import DashboardOverview
from ....services.dashboard import DashboardService
from ...dependencies.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(
    user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_db),
) -> dict:
    """Return organization-scoped aggregate KPIs for the requesting user.

    Any authenticated user may call this endpoint; each section is included
    only when the caller holds the corresponding module's read permission,
    so this never exposes data beyond what per-module endpoints already
    allow.
    """
    return DashboardService().overview(session, user)

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ....api.dependencies.auth import CurrentUser, get_current_user
from ....db import get_db
from ....permissions import permissions_for_roles
from ....schemas import CurrentUserRead, TokenResponse
from ....services.auth import AuthenticationService
from ....services.authorization import user_role_names

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=TokenResponse)
def issue_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db),
) -> TokenResponse:
    token = AuthenticationService().authenticate(
        session,
        email=form_data.username,
        password=form_data.password,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=CurrentUserRead)
def current_user(user: CurrentUser) -> CurrentUserRead:
    roles = user_role_names(user)
    return CurrentUserRead(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=roles,
        permissions=sorted(permissions_for_roles(roles)),
    )

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ....api.dependencies.auth import CurrentUser, get_current_user
from ....db import get_db
from ....permissions import permissions_for_roles
from ....schemas import (
    ChangePasswordRequest,
    CurrentUserRead,
    TokenResponse,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
)
from ....services.auth import AuthenticationService
from ....services.password_reset import PasswordResetService
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


@router.post("/change-password", status_code=204)
def change_password(
    request: ChangePasswordRequest,
    user: CurrentUser,
    session: Session = Depends(get_db),
) -> None:
    AuthenticationService().change_password(
        session,
        user=user,
        current_password=request.current_password,
        new_password=request.new_password,
    )


@router.post("/password-reset/request", status_code=202)
def request_password_reset(
    request: PasswordResetRequest,
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Request a reset without disclosing whether an account exists."""
    PasswordResetService().request_reset(
        session,
        email=request.email,
    )
    return {
        "message": (
            "If an account exists and password reset is available, "
            "instructions will be sent."
        )
    }


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    session: Session = Depends(get_db),
) -> None:
    """Consume a reset token and change the account password."""
    PasswordResetService().reset_password(
        session,
        token=request.token,
        new_password=request.new_password,
    )


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

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ...db import get_db
from ...exceptions import SecurityError
from ...models import User, UserStatus
from ...repositories import UserRepository
from ...security.tokens import decode_access_token
from ...permissions import has_cross_organization_permission
from ...services.authorization import has_permission, has_role, user_permissions

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    if not token:
        raise SecurityError("authentication_required", "Authentication is required", 401)
    try:
        user_id = decode_access_token(token)
    except (jwt.InvalidTokenError, ValueError):
        raise SecurityError("invalid_token", "Invalid authentication token", 401) from None
    user = UserRepository().get_by_id(session, user_id)
    if user is None:
        raise SecurityError("invalid_token", "Invalid authentication token", 401)
    if user.status is not UserStatus.ACTIVE:
        raise SecurityError("account_inactive", "Account is inactive", 401)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str) -> Callable:
    def dependency(user: CurrentUser) -> User:
        if not has_role(user, roles):
            raise SecurityError("permission_denied", "Permission denied", 403)
        return user

    return dependency


def require_permission(permission: str) -> Callable:
    def dependency(user: CurrentUser) -> User:
        if not has_permission(user, permission):
            raise SecurityError("permission_denied", "Permission denied", 403)
        return user

    return dependency


def organization_id_for_user(user: User) -> UUID:
    return user.organization_id


def ensure_organization_scope(user: User, organization_id: UUID) -> None:
    if organization_id == user.organization_id:
        return
    if has_cross_organization_permission(user_permissions(user)):
        return
    raise SecurityError("permission_denied", "Permission denied", 403)


def get_management_service():
    from ...services.management import ManagementService

    return ManagementService()


def get_device_management_service():
    from ...services.device_management import DeviceManagementService

    return DeviceManagementService()


def get_discovery_service():
    from ...services.discovery import DiscoveryService

    return DiscoveryService()


def get_diagnostic_service():
    from ...services.diagnostics import DiagnosticService

    return DiagnosticService()


def get_root_cause_service():
    from ...services.root_cause import RootCauseService

    return RootCauseService()


def get_recommendation_service():
    from ...services.recommendation import RecommendationService

    return RecommendationService()

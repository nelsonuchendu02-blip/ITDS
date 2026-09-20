from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...dependencies.auth import (
    ensure_organization_scope,
    get_management_service,
    require_permission,
)
from ....db import get_db
from ....exceptions import SecurityError
from ....models import Organization, User, UserStatus
from ....repositories import RoleRepository
from ....schemas import (
    AuditEventPage,
    AuditEventRead,
    OrganizationAdminRead,
    OrganizationUpdate,
    PageMeta,
    RoleAssignment,
    RoleRead,
    UserAdminRead,
    UserCreateAdmin,
    UserPage,
    UserUpdateAdmin,
)
from ....services import ManagementService
from ....services.authorization import has_permission, user_role_names

router = APIRouter(tags=["management"])
Service = Annotated[ManagementService, Depends(get_management_service)]


def _user_read(user: User) -> UserAdminRead:
    return UserAdminRead(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        roles=user_role_names(user),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/organizations/me", response_model=OrganizationAdminRead)
def get_my_organization(
    user: Annotated[User, Depends(require_permission("organizations:read"))],
    session: Session = Depends(get_db),
) -> OrganizationAdminRead:
    organization = session.get(Organization, user.organization_id)
    if organization is None:
        raise SecurityError("organization_not_found", "Organization not found", 404)
    return organization


@router.get("/organizations/{organization_id}", response_model=OrganizationAdminRead)
def get_organization(
    organization_id: UUID,
    user: Annotated[User, Depends(require_permission("organizations:read"))],
    service: Service,
    session: Session = Depends(get_db),
) -> OrganizationAdminRead:
    ensure_organization_scope(user, organization_id)
    organization = service.get_organization(session, organization_id)
    if organization is None:
        raise SecurityError("organization_not_found", "Organization not found", 404)
    return organization


@router.patch("/organizations/{organization_id}", response_model=OrganizationAdminRead)
def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdate,
    user: Annotated[User, Depends(require_permission("organizations:write"))],
    service: Service,
    session: Session = Depends(get_db),
) -> OrganizationAdminRead:
    ensure_organization_scope(user, organization_id)
    organization = service.get_organization(session, organization_id)
    if organization is None:
        raise SecurityError("organization_not_found", "Organization not found", 404)
    if payload.name is None:
        return organization
    return service.update_organization(
        session, organization=organization, name=payload.name, actor=user
    )


@router.get("/users", response_model=UserPage)
def list_users(
    user: Annotated[User, Depends(require_permission("users:read"))],
    service: Service,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    status: UserStatus | None = None,
    role: str | None = Query(default=None, min_length=1, max_length=100),
) -> UserPage:
    items, total = service.list_users(
        session, user.organization_id, offset=(page - 1) * page_size,
        limit=page_size, search=search, status=status.value if status else None, role=role,
    )
    return UserPage(
        items=[_user_read(item) for item in items],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.post("/users", response_model=UserAdminRead, status_code=201)
def create_user(
    payload: UserCreateAdmin,
    user: Annotated[User, Depends(require_permission("users:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> UserAdminRead:
    created = service.create_user(
        session, organization_id=user.organization_id, email=payload.email,
        display_name=payload.display_name, password=payload.password, actor=user,
    )
    return _user_read(created)


@router.get("/users/{user_id}", response_model=UserAdminRead)
def get_user(
    user_id: UUID,
    user: Annotated[User, Depends(require_permission("users:read"))],
    service: Service,
    session: Session = Depends(get_db),
) -> UserAdminRead:
    target = service.get_user(session, user.organization_id, user_id)
    if target is None:
        raise SecurityError("user_not_found", "User not found", 404)
    return _user_read(target)


@router.patch("/users/{user_id}", response_model=UserAdminRead)
def update_user(
    user_id: UUID,
    payload: UserUpdateAdmin,
    user: Annotated[User, Depends(require_permission("users:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> UserAdminRead:
    target = service.get_user(session, user.organization_id, user_id)
    if target is None:
        raise SecurityError("user_not_found", "User not found", 404)
    return _user_read(service.update_user(
        session, user=target, actor=user, email=payload.email, display_name=payload.display_name
    ))


def _set_status(
    user_id: UUID, status: UserStatus, actor: User, session: Session, service: ManagementService
) -> UserAdminRead:
    target = service.get_user(session, actor.organization_id, user_id)
    if target is None:
        raise SecurityError("user_not_found", "User not found", 404)
    if target.id == actor.id and status is UserStatus.INACTIVE:
        raise SecurityError("permission_denied", "Users cannot deactivate themselves", 403)
    return _user_read(service.set_user_status(session, user=target, actor=actor, status=status))


@router.post("/users/{user_id}/activate", response_model=UserAdminRead)
def activate_user(
    user_id: UUID,
    user: Annotated[User, Depends(require_permission("users:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> UserAdminRead:
    return _set_status(user_id, UserStatus.ACTIVE, user, session, service)


@router.post("/users/{user_id}/deactivate", response_model=UserAdminRead)
def deactivate_user(
    user_id: UUID,
    user: Annotated[User, Depends(require_permission("users:manage"))],
    service: Service,
    session: Session = Depends(get_db),
) -> UserAdminRead:
    return _set_status(user_id, UserStatus.INACTIVE, user, session, service)


@router.get("/users/{user_id}/roles", response_model=list[RoleRead])
def list_user_roles(
    user_id: UUID,
    user: Annotated[User, Depends(require_permission("roles:read"))],
    service: Service,
    session: Session = Depends(get_db),
) -> list[RoleRead]:
    target = service.get_user(session, user.organization_id, user_id)
    if target is None:
        raise SecurityError("user_not_found", "User not found", 404)
    return [RoleRead.model_validate(role) for role in target.roles]


@router.post("/users/{user_id}/roles", response_model=UserAdminRead)
def assign_role(
    user_id: UUID,
    payload: RoleAssignment,
    user: Annotated[User, Depends(require_permission("roles:assign"))],
    service: Service,
    session: Session = Depends(get_db),
) -> UserAdminRead:
    manager = service
    target = manager.get_user(session, user.organization_id, user_id)
    role = RoleRepository().get_by_id(session, user.organization_id, payload.role_id)
    if target is None or role is None:
        raise SecurityError("resource_not_found", "Resource not found", 404)
    if role.name == "platform_admin" and not has_permission(user, "organizations:cross_scope"):
        raise SecurityError("permission_denied", "Permission denied", 403)
    return _user_read(manager.assign_role(session, user=target, role=role, actor=user))


@router.delete("/users/{user_id}/roles/{role_id}", response_model=UserAdminRead)
def remove_role(
    user_id: UUID,
    role_id: UUID,
    user: Annotated[User, Depends(require_permission("roles:assign"))],
    service: Service,
    session: Session = Depends(get_db),
) -> UserAdminRead:
    manager = service
    target = manager.get_user(session, user.organization_id, user_id)
    role = RoleRepository().get_by_id(session, user.organization_id, role_id)
    if target is None or role is None:
        raise SecurityError("resource_not_found", "Resource not found", 404)
    return _user_read(manager.remove_role(session, user=target, role=role, actor=user))


@router.get("/audit-events", response_model=AuditEventPage)
def list_audit_events(
    user: Annotated[User, Depends(require_permission("audit:read"))],
    service: Service,
    session: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    event_type: str | None = Query(default=None, min_length=1, max_length=100),
    actor_user_id: UUID | None = None,
) -> AuditEventPage:
    items, total = service.list_audit_events(
        session, user.organization_id, offset=(page - 1) * page_size,
        limit=page_size, event_type=event_type, actor_user_id=actor_user_id,
    )
    return AuditEventPage(
        items=[AuditEventRead.model_validate(item) for item in items],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )

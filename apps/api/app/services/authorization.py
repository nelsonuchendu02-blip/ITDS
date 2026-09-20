from collections.abc import Iterable

from ..models import User
from ..permissions import permissions_for_roles


def user_role_names(user: User) -> list[str]:
    return sorted(role.name for role in user.roles)


def user_permissions(user: User) -> set[str]:
    return permissions_for_roles(user_role_names(user))


def has_permission(user: User, permission: str) -> bool:
    permissions = user_permissions(user)
    if permission == "organizations:cross_scope":
        return permission in permissions
    return "*" in permissions or permission in permissions


def has_role(user: User, roles: Iterable[str]) -> bool:
    allowed = set(roles)
    return bool(allowed.intersection(user_role_names(user)))

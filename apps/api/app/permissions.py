from collections.abc import Iterable

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "platform_admin": frozenset({"*"}),
    "organization_admin": frozenset({"users:read", "users:write", "users:manage", "audit:read"}),
    "it_support": frozenset({"users:read", "devices:read", "devices:write", "audit:read"}),
    "technician": frozenset({"devices:read", "devices:write", "diagnostics:run"}),
    "viewer": frozenset({"users:read", "devices:read"}),
}
ORG_CROSS_SCOPE_PERMISSION = "organizations:cross_scope"

BASELINE_ROLES = tuple(ROLE_PERMISSIONS)


def permissions_for_roles(role_names: Iterable[str]) -> set[str]:
    permissions: set[str] = set()
    for role_name in role_names:
        permissions.update(ROLE_PERMISSIONS.get(role_name, ()))
    return permissions


def has_cross_organization_permission(permissions: set[str]) -> bool:
    return ORG_CROSS_SCOPE_PERMISSION in permissions

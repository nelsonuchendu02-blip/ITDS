from collections.abc import Iterable

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "platform_admin": frozenset({"*"}),
    "organization_admin": frozenset(
        {
            "organizations:read",
            "organizations:write",
            "organizations:manage",
            "users:read",
            "users:write",
            "users:manage",
            "devices:read",
            "devices:write",
            "devices:manage",
            "assets:read", "assets:create", "assets:manage",
            "networks:read", "networks:create", "networks:manage",
            "discovery:read",
            "discovery:run",
            "discovery:manage",
            "diagnostics:read",
            "diagnostics:run",
            "diagnostics:manage",
            "root_cause:read",
            "root_cause:run",
            "root_cause:manage",
            "recommendations:read",
            "recommendations:run",
            "recommendations:manage",
            "remediation:read", "remediation:create", "remediation:approve",
            "remediation:execute", "remediation:manage", "remediation:verify",
            "incidents:read", "incidents:create", "incidents:manage",
            "incidents:assign", "incidents:resolve", "incidents:close",
            "escalations:read", "escalations:create", "escalations:manage",
            "escalations:resolve",
            "roles:read",
            "roles:assign",
            "audit:read",
        }
    ),
    "it_support": frozenset(
        {"users:read", "devices:read", "devices:write",
         "assets:read", "assets:create", "networks:read", "networks:create",
         "discovery:read", "discovery:run",
         "root_cause:read", "root_cause:run", "recommendations:read", "recommendations:run",
         "incidents:read", "incidents:create", "escalations:read", "escalations:create", "audit:read"}
    ),
    "technician": frozenset({"devices:read", "devices:write", "assets:read", "assets:create",
                             "networks:read", "networks:create", "diagnostics:read", "diagnostics:run",
                             "root_cause:read", "root_cause:run", "recommendations:read",
                             "recommendations:run", "remediation:read", "remediation:create",
                             "remediation:verify", "incidents:read", "incidents:create",
                             "incidents:assign", "escalations:read", "escalations:create"}),
    "viewer": frozenset({"users:read", "devices:read", "assets:read", "networks:read"}),
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

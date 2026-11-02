"""The one place that says which role can do what. Use `require_permission` in routes, not role names."""

STAFF_ROLES = frozenset({"staff", "admin", "superadmin"})

_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "superadmin": frozenset({
        "manage_admins", "manage_plans", "view_revenue", "verify_accounts", "remove_reported", "approve_ads",
        "resolve_tickets", "moderate_first_level",
    }),
    "admin": frozenset({"verify_accounts", "remove_reported", "approve_ads", "resolve_tickets", "moderate_first_level"}),
    "staff": frozenset({"resolve_tickets", "moderate_first_level", "escalate"}),
    "business": frozenset({"manage_business"}),
    "user": frozenset(),
}


def permissions_of(role: str) -> frozenset[str]:
    return _ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: str, permission: str) -> bool:
    return permission in permissions_of(role)

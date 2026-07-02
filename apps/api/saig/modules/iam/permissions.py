"""Permission catalog and system roles.

`resource:action` codes per the security architecture. The catalog grows
per module; the seed script upserts it idempotently.
"""

PERMISSION_CATALOG: dict[str, str] = {
    "users:read": "View users",
    "users:manage": "Create, update, deactivate and delete users",
    "roles:manage": "Manage roles and their permissions",
    "org:manage": "Manage organization settings and departments",
    "audit:read": "View audit logs",
}

# System roles are seeded per organization and cannot be edited or deleted.
SYSTEM_ROLES: dict[str, list[str]] = {
    "Administrator": list(PERMISSION_CATALOG.keys()),
    "Viewer": ["users:read"],
}

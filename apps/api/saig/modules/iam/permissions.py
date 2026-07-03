"""Permission catalog and system roles.

`resource:action` codes per the security architecture. The catalog grows
per module; the seed script upserts it idempotently.
"""

PERMISSION_CATALOG: dict[str, str] = {
    # IAM (Phase 0)
    "users:read": "View users",
    "users:manage": "Create, update, deactivate and delete users",
    "roles:manage": "Manage roles and their permissions",
    "org:manage": "Manage organization settings and departments",
    "audit:read": "View audit logs",
    # Field operations (Phase 1)
    "regions:manage": "Manage operating regions",
    "farmers:read": "View farmers (PII masked)",
    "farmers:read_pii": "View farmer personal data (national ID, phone, email)",
    "farmers:create": "Register farmers",
    "farmers:update": "Update farmers and production history",
    "farmers:delete": "Delete farmers",
    "farms:read": "View farms, fields and soil data",
    "farms:manage": "Create and manage farms, fields and soil data",
    "crops:read": "View crop cycles",
    "crops:manage": "Create crop cycles and record stage transitions",
    # Seed catalog (Phase 1)
    "varieties:read": "View the seed variety catalog",
    "varieties:manage": "Manage seed varieties and region suitability",
}

# System roles are seeded per organization and cannot be edited or deleted.
SYSTEM_ROLES: dict[str, list[str]] = {
    "Administrator": list(PERMISSION_CATALOG.keys()),
    "Viewer": [
        "users:read",
        "farmers:read",
        "farms:read",
        "crops:read",
        "varieties:read",
    ],
    "Field Officer": [
        "farmers:read",
        "farmers:create",
        "farmers:update",
        "farms:read",
        "farms:manage",
        "crops:read",
        "crops:manage",
        "varieties:read",
    ],
    "Agronomist": [
        "farmers:read",
        "farms:read",
        "farms:manage",
        "crops:read",
        "crops:manage",
        "varieties:read",
        "varieties:manage",
    ],
}

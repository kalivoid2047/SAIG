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
    # Weather & crop health (Phase 2)
    "weather:read": "View weather forecasts, history and agro-indicators",
    "crops:report": "File crop disease reports",
    "crops:confirm": "Confirm, treat and resolve disease reports",
    # Inventory (Phase 2)
    "inventory:read": "View warehouses, stock and transfers",
    "inventory:manage": "Manage warehouses and stock lots",
    "inventory:move": "Record stock receipts, adjustments and write-offs",
    "inventory:transfer": "Create and process stock transfers",
    # Supply chain (Phase 2)
    "logistics:read": "View vehicles, orders, routes and deliveries",
    "logistics:manage": "Manage vehicles and customer orders",
    "logistics:plan": "Plan and dispatch delivery routes",
    "logistics:track": "Record delivery check-ins and status updates",
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
        "weather:read",
        "inventory:read",
    ],
    "Field Officer": [
        "farmers:read",
        "farmers:create",
        "farmers:update",
        "farms:read",
        "farms:manage",
        "crops:read",
        "crops:manage",
        "crops:report",
        "varieties:read",
        "weather:read",
    ],
    "Agronomist": [
        "farmers:read",
        "farms:read",
        "farms:manage",
        "crops:read",
        "crops:manage",
        "crops:report",
        "crops:confirm",
        "varieties:read",
        "varieties:manage",
        "weather:read",
    ],
    "Warehouse Manager": [
        "inventory:read",
        "inventory:manage",
        "inventory:move",
        "inventory:transfer",
        "varieties:read",
    ],
    "Supply Chain Manager": [
        "logistics:read",
        "logistics:manage",
        "logistics:plan",
        "inventory:read",
        "varieties:read",
        "farms:read",
    ],
    "Driver": [
        "logistics:read",
        "logistics:track",
    ],
}

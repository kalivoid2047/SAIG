# API Specification

**Base URL:** `/api/v1` · **Auth:** `Authorization: Bearer <access JWT>` unless marked public · **Content type:** `application/json` (uploads: `multipart/form-data`).

All request/response shapes are defined as Zod schemas in `packages/contracts` — that package is the machine-readable contract; this document is the human-readable map. OpenAPI 3.1 is generated from the contracts in CI (`docs/openapi.json`).

## Conventions

- **IDs:** UUID v4. **Times:** ISO-8601 UTC.
- **Pagination:** `?page=1&pageSize=25` (max 100) → `{ data: [...], meta: { page, pageSize, totalItems, totalPages } }`.
- **Filtering/sorting:** documented per endpoint; `?sort=field:asc|desc`.
- **Errors:** RFC 7807 `application/problem+json`:
  ```json
  { "type": "https://saig.dev/errors/validation", "title": "Validation failed",
    "status": 422, "detail": "…", "instance": "/api/v1/farmers",
    "requestId": "…", "errors": [{ "path": "phone", "message": "…" }] }
  ```
- **Status codes:** 200 read, 201 create (+`Location`), 204 delete, 400 malformed, 401 unauthenticated, 403 forbidden, 404 not found (also for cross-org access — no existence leaks), 409 conflict, 422 validation, 429 rate-limited.
- **Idempotency:** mutating endpoints accept `Idempotency-Key` header (stored 24 h).
- **Permissions:** listed per route as `resource:action`.

---

## Auth — `/auth` (public unless noted)

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /auth/login` | Sign in | → `{ accessToken, user }` + refresh cookie; 423 when locked |
| `POST /auth/refresh` | Rotate tokens | Reads httpOnly cookie; reuse → 401 + family revoked |
| `POST /auth/logout` | Revoke session | auth required |
| `POST /auth/forgot-password` | Request reset | Always 202 (no enumeration) |
| `POST /auth/reset-password` | Consume reset token | Invalidates all sessions |
| `GET /auth/me` | Current user + permissions | auth required |

## Users & Org — `/organizations`, `/departments`, `/roles`, `/users`

| Method & path | Permission |
|---|---|
| `GET/POST /users` · `GET/PATCH/DELETE /users/:id` | `users:read` / `users:manage` |
| `POST /users/:id/activate` · `POST /users/:id/deactivate` | `users:manage` (deactivate kills sessions) |
| `PATCH /users/me` (profile, locale, timezone) | any authenticated |
| `GET/POST /roles` · `GET/PATCH/DELETE /roles/:id` | `roles:manage` |
| `GET /permissions` (catalog) | `roles:manage` |
| `GET/POST /departments` · `PATCH/DELETE /departments/:id` | `org:manage` |
| `GET /audit-logs?entityType&entityId&actorId&from&to` | `audit:read` |

## Farmers — `/farmers`

| Method & path | Permission | Notes |
|---|---|---|
| `GET /farmers?search&regionId&riskMin` | `farmers:read` | PII fields masked without `farmers:read_pii` |
| `POST /farmers` | `farmers:create` | 409 on duplicate national ID/phone with existing ID |
| `GET /farmers/:id` | `farmers:read` | includes latest risk score + farms summary |
| `PATCH /farmers/:id` · `DELETE /farmers/:id` | `farmers:update` / `farmers:delete` | delete = soft |
| `GET /farmers/:id/production-records` · `POST …` | `farmers:read` / `farmers:update` | |
| `GET /farmers/:id/risk-history` | `farmers:read` | |
| `GET /farmers/:id/insights` | `farmers:read` | cached AI summary + generated-at |

## Farms & Fields — `/farms`, `/fields`, `/crop-cycles`

| Method & path | Permission | Notes |
|---|---|---|
| `GET/POST /farms` · `GET/PATCH/DELETE /farms/:id` | `farms:*` | GeoJSON in/out for geometry |
| `GET/POST /farms/:id/fields` · `PATCH/DELETE /fields/:id` | `farms:*` | area derived server-side from polygon |
| `GET/POST /fields/:id/soil-samples` | `farms:read/update` | |
| `POST /fields/:id/crop-cycles` | `crops:create` | 409 if active cycle exists for season |
| `GET /crop-cycles?status&season&regionId` · `GET /crop-cycles/:id` | `crops:read` | detail embeds latest prediction + observations |
| `POST /crop-cycles/:id/transitions` | `crops:update` | body `{ to: 'planted'…, actualYieldKg? }`; invalid transition → 422 |
| `POST /crop-cycles/:id/observations` | `crops:update` | |
| `POST /attachments` (multipart) | contextual | `{ entityType, entityId, file }` → scanned, stored, 201 |

## Seed Varieties — `/varieties`

CRUD (`varieties:read|manage`) + `GET /varieties/:id/suitability` and `PUT /varieties/:id/suitability` (region-score matrix) + `POST /varieties/recommendations` (body: fieldId or soil/climate params → ranked varieties with rationale).

## Weather — `/weather`

| Method & path | Notes |
|---|---|
| `GET /weather/forecast?farmId` or `?lat&lng` | 14-day daily forecast + staleness metadata |
| `GET /weather/history?farmId&from&to&metrics` | daily observations |
| `GET /weather/aggregates?farmId&window=30\|60\|90` | rainfall sum, GDD, heat-stress days |
| `GET /climate/indicators?regionId` | drought/flood/heat probability+severity |
| `GET /climate/trends?regionId&years=5` | anomaly series |

Permission: `weather:read`.

## Crop Health — `/disease-reports`, `/diseases`

| Method & path | Permission | Notes |
|---|---|---|
| `GET /diseases` | `crops:read` | catalog |
| `POST /disease-reports` | `crops:report` | triggers outbreak scan (async) |
| `GET /disease-reports?status&diseaseId&regionId&bbox&from&to` | `crops:read` | |
| `POST /disease-reports/:id/transitions` | `crops:confirm` | reported→confirmed→treated→resolved |
| `GET /disease-reports/heatmap?bbox&from&to` | `crops:read` | aggregated GeoJSON for map layer |

## Inventory — `/warehouses`, `/stock`

| Method & path | Permission | Notes |
|---|---|---|
| `GET/POST /warehouses` · `GET/PATCH/DELETE /warehouses/:id` | `inventory:read/manage` | |
| `GET /stock/balances?warehouseId&varietyId&expiringWithinDays` | `inventory:read` | from ledger view; FEFO ordering |
| `GET/POST /stock/lots` | `inventory:read/manage` | |
| `POST /stock/movements` | `inventory:move` | receipt/adjustment/write-off; 422 if balance would go negative |
| `GET /stock/movements?warehouseId&lotId&from&to` | `inventory:read` | immutable history |
| `POST /stock/transfers` | `inventory:transfer` | validates availability |
| `POST /stock/transfers/:id/dispatch` · `POST …/:id/receive` | `inventory:transfer` | receive body `{ receivedKg }`; variance auto-flagged |
| `GET /stock/coverage?regionId` | `inventory:read` | coverage vs. 90-day forecast |
| `GET /stock/forecast?warehouseId&varietyId` | `inventory:read` | projected stock curve |

## Supply Chain — `/vehicles`, `/orders`, `/routes`, `/deliveries`

| Method & path | Permission | Notes |
|---|---|---|
| `GET/POST /vehicles` · `PATCH /vehicles/:id` | `logistics:*` | |
| `GET/POST /orders` · `GET/PATCH /orders/:id` | `orders:*` | items embedded |
| `POST /routes` | `logistics:plan` | body: warehouse, date, orderIds |
| `POST /routes/optimize` | `logistics:plan` | calls ML VRP; returns plan + savings; 202 + polling if slow |
| `PATCH /routes/:id/stops` | `logistics:plan` | manual resequencing (draft only) |
| `POST /routes/:id/dispatch` | `logistics:dispatch` | creates deliveries, sets vehicle on_route |
| `GET /deliveries?status&routeId` · `GET /deliveries/:id` | `logistics:read` | with event trail |
| `POST /deliveries/:id/events` | `logistics:track` | status change / location ping (driver check-in) |

## Forecasts & Predictions — `/forecasts`, `/predictions`

| Method & path | Permission | Notes |
|---|---|---|
| `GET /forecasts/demand?regionId&varietyId&horizon=12` | `forecasts:read` | latest run; intervals + confidence |
| `GET /forecasts/demand/accuracy?segment` | `forecasts:read` | MAPE vs. actuals |
| `GET /predictions/yield?cropCycleId` · `?regionId&season` (aggregated) | `forecasts:read` | |
| `POST /predictions/yield/rescore` | `forecasts:trigger` | body: cropCycleIds[]; 202 + job id |
| `GET /models?name` | `models:read` | registry: versions, metrics, status |
| `GET /jobs/:id` | any authenticated | generic async-job status endpoint |

## Risk & Recommendations — `/risks`, `/recommendations`

| Method & path | Permission | Notes |
|---|---|---|
| `GET /risks/board` | `risks:read` | 6 domains × scope, latest + trend |
| `GET /risks?domain&regionId&from&to` | `risks:read` | history |
| `GET /risks/:id/factors` | `risks:read` | factor breakdown + entity drill-down links |
| `GET /recommendations?status&category&urgency` | `recommendations:read` | |
| `POST /recommendations/:id/decision` | `recommendations:decide` | `{ decision: 'accepted'\|'dismissed', note? }` |
| `POST /recommendations/:id/complete` | `recommendations:decide` | |
| `GET /recommendations/analytics` | `recommendations:read` | acceptance rates per category |

## Copilot — `/copilot`

| Method & path | Permission | Notes |
|---|---|---|
| `GET/POST /copilot/conversations` · `PATCH/DELETE …/:id` | `copilot:use` | |
| `POST /copilot/conversations/:id/messages` | `copilot:use` | **SSE stream**: tokens → citations → chart spec → done; rate-limited 20/min |
| `GET /copilot/conversations/:id/messages` | `copilot:use` | history with citations + executed SQL (if `copilot:audit`) |
| `GET /copilot/usage` | `copilot:use` (own) / `copilot:admin` (org) | token budgets + spend |

## Documents — `/documents`

| Method & path | Permission | Notes |
|---|---|---|
| `POST /documents` (multipart) | `documents:upload` | ≤50 MB; → 201 status `processing` |
| `GET /documents?type&status&search` · `GET/DELETE /documents/:id` | `documents:read/manage` | |
| `POST /documents/search` | `documents:read` | `{ query, topK }` → chunks with scores + doc refs (RBAC-filtered) |

## Scenarios — `/scenarios`

CRUD (`scenarios:*`) + `POST /scenarios/:id/run` (202 + job) + `GET /scenarios/compare?ids=a,b` (aligned delta table).

## GIS — `/gis`

| Method & path | Notes |
|---|---|
| `GET /gis/farms?bbox&zoom` | clustered GeoJSON (server-side clustering above zoom threshold) |
| `GET /gis/fields?bbox` | field polygons |
| `GET /gis/warehouses?bbox` · `GET /gis/routes/active` | markers / linestrings |
| `GET /gis/layers/disease?bbox&from&to` · `GET /gis/layers/weather?metric` | overlay data |

All `gis:read`; payload per viewport capped (FR-GIS-3).

## Notifications — `/notifications`

`GET /notifications?unreadOnly` · `POST /notifications/:id/read` · `POST /notifications/read-all` · `POST /notifications/:id/acknowledge` · `GET/PUT /notifications/preferences` (category × channel matrix).

## Reports — `/reports`

`POST /reports/generate` (`{ type, format, parameters }` → 202 + job → artifact link) · `GET /reports/artifacts` · `GET/POST /reports/subscriptions` · `PATCH/DELETE /reports/subscriptions/:id` · `POST /reports/export` (grid export: `{ resource, filters, format }`).

## Dashboard — `/dashboard`

`GET /dashboard/kpis?regionId&from&to` · `GET /dashboard/widgets/:widget` (yield-trend, demand-by-region, risk-map, low-stock, latest-recommendations) · `GET/PUT /dashboard/layout` (per-user widget layout).

---

## WebSocket (Socket.IO)

Namespace `/alerts` (JWT in handshake auth):

| Event (server→client) | Payload |
|---|---|
| `alert:new` | `{ id, category, severity, title, deepLink, createdAt }` |
| `risk:threshold` | `{ domain, regionId, score, previous }` |
| `delivery:update` | `{ deliveryId, status, location? }` |
| `job:completed` | `{ jobId, type, result }` (rescore, scenario, report) |

Rooms: `user:<id>`, `role:<roleId>`, `org:<orgId>` — server routes events by audience.

## ML Service internal API (not exposed publicly)

`POST /v1/predict/yield` · `POST /v1/forecast/demand` · `POST /v1/risk/disease` · `POST /v1/optimize/routes` · `POST /v1/simulate` · `GET /v1/health`. Auth: network isolation + service token; contracts mirrored in `apps/ml/app/schemas`.

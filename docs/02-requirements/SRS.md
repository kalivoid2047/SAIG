# Software Requirements Specification (SRS)

**System:** SeedCo Agro Intelligence Grid (SAIG) · **Version:** 1.0.0 · **Standard:** Adapted from IEEE 830/29148

---

## 1. Introduction

### 1.1 Purpose
This SRS defines the complete functional and non-functional requirements for SAIG. It is the contract between business stakeholders and the engineering team; every implemented behavior must trace to a requirement here, and every requirement traces to the BRD/PRD.

### 1.2 Definitions

| Term | Definition |
|------|-----------|
| Crop cycle | One planting-to-harvest lifecycle of a variety on a field |
| Lot | A batch of seed stock with shared production date and expiry |
| Risk score | 0–100 normalized score per risk domain, higher = worse |
| Confidence score | 0–1 model self-assessment of prediction reliability |
| Semantic layer | Curated read-only SQL views exposed to the copilot |
| Grounded answer | Copilot answer where every factual claim cites a queried source |

### 1.3 System Context
SAIG comprises: a React SPA, a Node.js/Express API (modular monolith), a Python FastAPI ML service, Supabase PostgreSQL (PostGIS, pgvector), Redis (cache + BullMQ queues), Socket.IO for realtime, and integrations: OpenAI API, weather provider, email/SMS providers, Power BI.

---

## 2. Overall Description

- **Users:** see PRD personas. All access is authenticated; capabilities derive from RBAC permissions.
- **Operating environment:** modern evergreen browsers (Chrome/Edge/Firefox/Safari, last 2 versions), responsive from 360 px; servers containerized on AWS.
- **Design constraints:** tech stack fixed per project charter; farmer PII never leaves the platform boundary (never sent to external LLMs); all diagrams/services must be reproducible via IaC.

---

## 3. Functional Requirements

Requirement IDs: `FR-<module>-<n>`. Priority: **M**ust / **S**hould / **C**ould (MoSCoW).

### 3.1 Module 1 — Executive Dashboard
- **FR-DASH-1 (M)** Display KPI cards: production YTD vs target, forecast revenue (next quarter), total inventory value, active high risks, on-time delivery %, active farmers. Values sourced from materialized views refreshed ≤ 15 min.
- **FR-DASH-2 (M)** Display widgets: yield forecast trend, demand forecast by region, climate-risk map snapshot, low-stock list (top 10), latest recommendations (top 5), real-time alert feed.
- **FR-DASH-3 (M)** Global filters (date range, organization unit, region) apply to all widgets and persist per user.
- **FR-DASH-4 (S)** Widget layout customizable per user (show/hide, reorder).

### 3.2 Module 2 — Authentication
- **FR-AUTH-1 (M)** Email/password sign-in; passwords hashed with Argon2id (memory ≥ 64 MB, iterations tuned to ≥ 250 ms).
- **FR-AUTH-2 (M)** Access JWT lifetime 15 min; refresh token 7 days, httpOnly+Secure+SameSite=Strict cookie, **rotated on every use**, reuse detection revokes the token family.
- **FR-AUTH-3 (M)** RBAC: permissions as `resource:action`; roles bundle permissions; users↔roles many-to-many; permission checks enforced server-side per route.
- **FR-AUTH-4 (M)** Account lockout: 5 failures/15 min → 15 min lock; all auth events audit-logged.
- **FR-AUTH-5 (M)** Password reset via single-use, 30-min expiring token; sessions invalidated on reset.
- **FR-AUTH-6 (S)** MFA-ready: TOTP enrollment/verification data model and hooks present; enforcement configurable per role.
- **FR-AUTH-7 (M)** Logout revokes refresh token server-side.

### 3.3 Module 3 — User Management
- **FR-USER-1 (M)** CRUD for organizations, departments, roles, permissions, users; users belong to one organization and optionally one department.
- **FR-USER-2 (M)** Admins may deactivate users (soft); deactivation kills active sessions ≤ 60 s.
- **FR-USER-3 (M)** Profile self-service: name, avatar, locale, timezone, notification preferences.
- **FR-USER-4 (S)** Role changes take effect without re-login (permission cache TTL ≤ 60 s).

### 3.4 Module 4 — Farmer Management
- **FR-FRM-1 (M)** Farmer profile: identity, contacts, region, cooperative membership, registration metadata; duplicate detection on national ID/phone.
- **FR-FRM-2 (M)** Historical production records per farmer (season, variety, area, yield).
- **FR-FRM-3 (M)** Farmer risk score (0–100) recomputed on schedule and on relevant events; factors stored with the score.
- **FR-FRM-4 (S)** AI insight summary per farmer (generated from structured data; cached; regenerated on material change).
- **FR-FRM-5 (M)** PII fields access-controlled by dedicated permission `farmers:read_pii`; all PII reads audit-logged.

### 3.5 Module 5 — Farm Management
- **FR-FARM-1 (M)** Farms belong to farmers; fields belong to farms; fields store PostGIS polygon boundaries and auto-computed area.
- **FR-FARM-2 (M)** Soil records per field: pH, N/P/K, organic matter, texture, sample date, source.
- **FR-FARM-3 (M)** Crop cycles per field: variety, planting date, expected/actual harvest, practices (irrigation, fertilizer), status lifecycle (planned → planted → growing → harvested → failed).
- **FR-FARM-4 (M)** Image attachments (farm/field/crop) stored in object storage; metadata in DB; max 10 MB/image; EXIF GPS extracted when present.
- **FR-FARM-5 (S)** Field health report aggregating latest observations, weather stress, and predictions.

### 3.6 Module 6 — Weather Intelligence
- **FR-WX-1 (M)** Scheduled ingestion of forecasts (hourly/daily, 14-day horizon) and observed weather for all distinct farm locations, deduplicated by geo-grid cell (~5 km) to bound API cost.
- **FR-WX-2 (M)** Historical weather store enabling rolling aggregates (7/30/90-day rainfall, GDD, heat-stress days).
- **FR-WX-3 (M)** Climate-risk analysis per region: drought, flood, heat-wave indicators with probability + severity, computed daily.
- **FR-WX-4 (M)** Weather data staleness surfaced in UI; ingestion failures alert operations.
- **FR-WX-5 (S)** Climate trend view: multi-year anomalies per region.

### 3.7 Module 7 — Crop Intelligence
- **FR-CROP-1 (M)** Growth-stage observations per crop cycle (stage, health rating, notes, photos).
- **FR-CROP-2 (M)** Disease reports: catalog-linked disease, severity 1–5, affected %, photos, geotag; status workflow (reported → confirmed → treated → resolved).
- **FR-CROP-3 (M)** Outbreak detection: ≥ 3 same-disease reports within 10 km/7 days escalates and alerts (parameters configurable).
- **FR-CROP-4 (M)** Yield prediction display per crop cycle with interval + confidence + model version (engine in Module 12).
- **FR-CROP-5 (S)** AI treatment/practice recommendations linked to disease + variety + stage.

### 3.8 Module 8 — Seed Variety Management
- **FR-SEED-1 (M)** Variety catalog: crop, maturity days, yield potential, drought/disease tolerance ratings, certifications.
- **FR-SEED-2 (M)** Region suitability matrix (variety × region × score with rationale).
- **FR-SEED-3 (S)** Variety recommendation for a field given soil + climate + objectives.

### 3.9 Module 9 — Inventory Management
- **FR-INV-1 (M)** Warehouses with location (PostGIS point), capacity, manager.
- **FR-INV-2 (M)** Stock as append-only movements (receipt, dispatch, transfer-out/in, adjustment, write-off) over lots; current balance = derived view; balance can never be driven negative (enforced transactionally).
- **FR-INV-3 (M)** Lot tracking: production date, expiry, germination-test results; FEFO ordering surfaced at dispatch.
- **FR-INV-4 (M)** Transfers per UC-06 with in-transit state and variance capture.
- **FR-INV-5 (M)** Alerts: low stock vs. forecast coverage, near-expiry (configurable horizons).
- **FR-INV-6 (S)** Inventory forecast: projected stock curve per warehouse × variety from demand forecast + planned receipts.

### 3.10 Module 10 — Supply Chain Intelligence
- **FR-SC-1 (M)** Vehicle registry (capacity, status); driver assignment.
- **FR-SC-2 (M)** Orders → deliveries with lifecycle (pending → assigned → in-transit → delivered/failed) and timestamped events.
- **FR-SC-3 (M)** Route plans: ordered stops, distances, ETAs; manual editing before dispatch.
- **FR-SC-4 (S)** Route optimization (VRP: capacity + time windows) via ML service; savings vs. naive plan reported.
- **FR-SC-5 (S)** Delivery tracking updates via driver check-ins (status + location ping); map layer shows active routes.

### 3.11 Module 11 — Demand Forecasting
- **FR-DEM-1 (M)** Historical sales ingestion (region, variety, channel, month).
- **FR-DEM-2 (M)** Monthly demand forecast per region × variety, 12-month horizon, retrained/re-scored monthly; outputs include seasonal components and confidence intervals.
- **FR-DEM-3 (M)** Forecast vs. actual tracking with MAPE per segment; visible to planners.
- **FR-DEM-4 (S)** External signal inputs (weather outlook, economic indicators) as optional features, recorded in lineage.

### 3.12 Module 12 — Yield Prediction Engine
- **FR-YLD-1 (M)** Nightly batch scoring of active crop cycles per UC-04; on-demand re-score allowed.
- **FR-YLD-2 (M)** Output: predicted yield/ha, 80% interval, confidence 0–1, model version, feature snapshot reference. Predictions immutable; new runs append.
- **FR-YLD-3 (M)** Regional/organizational aggregation views weighted by field area.
- **FR-YLD-4 (M)** Model registry: version, training window, metrics; only "promoted" versions serve.
- **FR-YLD-5 (S)** Feature-importance explanation stored per model version and exposed in UI.

### 3.13 Module 13 — Risk Intelligence
- **FR-RISK-1 (M)** Daily risk scores per domain (climate, disease, supply-chain, inventory, production, financial) at region + organization scope; factors with weights stored alongside.
- **FR-RISK-2 (M)** Threshold-crossing emits alert events (Module 19) and evaluates recommendation rules (Module 14).
- **FR-RISK-3 (M)** Risk history retained for trend visualization.
- **FR-RISK-4 (S)** Drill-down from score → factors → underlying entities (farms, warehouses, routes).

### 3.14 Module 14 — Recommendation Engine
- **FR-REC-1 (M)** Recommendations generated from rule evaluation over risks/forecasts and from AI synthesis; each stores: title, narrative rationale, expected impact, urgency, evidence links (risk/forecast/report IDs), generator (rule ID or model+prompt version).
- **FR-REC-2 (M)** Lifecycle: proposed → accepted | dismissed → completed; every transition records user + timestamp + optional note.
- **FR-REC-3 (M)** Acceptance-rate and outcome analytics per category.
- **FR-REC-4 (S)** Feedback loop: dismissal reasons feed rule/prompt tuning review.

### 3.15 Module 15 — AI Executive Copilot
- **FR-AI-1 (M)** Chat UI with streaming responses, conversation history per user, rename/delete conversations.
- **FR-AI-2 (M)** Intent routing: data query | document QA | forecast lookup | simulation trigger | out-of-scope.
- **FR-AI-3 (M)** Data queries: LLM-generated SQL restricted to the semantic layer (allow-listed views), SELECT-only, enforced row limit, executed under read-only DB role, statement timeout ≤ 5 s; generated SQL logged.
- **FR-AI-4 (M)** Every factual answer carries citations (view names / document chunks); the copilot must refuse when grounding fails (no free-form numeric claims).
- **FR-AI-5 (M)** Quantitative answers include a chart specification rendered by the client (Recharts).
- **FR-AI-6 (M)** Farmer PII excluded from the semantic layer and from prompts.
- **FR-AI-7 (S)** Tool-calling to run saved scenario simulations and fetch forecasts.
- **FR-AI-8 (M)** Per-user and per-org token budgets with graceful degradation and admin visibility.

### 3.16 Module 16 — Document Intelligence
- **FR-DOC-1 (M)** Upload PDF/DOCX/XLSX (≤ 50 MB); virus-scan; extract text; chunk (~800 tokens, 15% overlap); embed to pgvector; index within 5 min.
- **FR-DOC-2 (M)** Semantic search with hybrid retrieval (vector + keyword), RBAC-filtered at query time.
- **FR-DOC-3 (M)** Document QA in copilot with chunk-level citations (doc title + section).
- **FR-DOC-4 (S)** Collections/tags; re-index on new embedding model version.

### 3.17 Module 17 — Scenario Simulator
- **FR-SIM-1 (M)** Scenario templates: rainfall change, demand shock, production delay, disease outbreak; parameterized (region, magnitude, horizon).
- **FR-SIM-2 (M)** Simulation = baseline snapshot + perturbed re-scoring via ML service; outputs deltas for yield, demand, stock coverage, revenue.
- **FR-SIM-3 (M)** Scenarios saved, named, versioned, comparable side-by-side, exportable.
- **FR-SIM-4 (C)** Compound scenarios (multiple simultaneous shocks).

### 3.18 Module 18 — GIS
- **FR-GIS-1 (M)** Leaflet map with layers: farms (clustered markers), field polygons, warehouses, disease heat-map, weather overlay, active routes; layer toggles; region filter synchronized with global filters.
- **FR-GIS-2 (M)** Feature click → context card with deep link to entity page.
- **FR-GIS-3 (S)** Server-side geo queries (bbox/viewport loading) to keep payloads < 1 MB per viewport.

### 3.19 Module 19 — Notifications
- **FR-NOT-1 (M)** Channels: in-app real-time (Socket.IO), email; SMS and web push in Phase 5. Category × channel preference matrix per user.
- **FR-NOT-2 (M)** Alert events (risk threshold, low stock, outbreak, delivery failure, system) produce notifications through a single dispatch pipeline (BullMQ) with retry + dead-letter queue.
- **FR-NOT-3 (M)** Every notification deep-links to its context; read/acknowledged states tracked.
- **FR-NOT-4 (S)** Digest mode (daily summary) and escalation (unacknowledged critical → next channel after N min).

### 3.20 Module 20 — Reporting
- **FR-RPT-1 (M)** On-demand export of any module's filtered data grid as CSV/Excel.
- **FR-RPT-2 (M)** Composed PDF reports (executive pack, inventory, risk) from templates.
- **FR-RPT-3 (M)** Scheduled reports (cron per subscription) delivered by email with signed, expiring links.
- **FR-RPT-4 (S)** Power BI integration via read-only reporting schema + service credentials.

---

## 4. Non-Functional Requirements

### 4.1 Performance
- **NFR-P1** p95 API latency < 300 ms for CRUD, < 500 ms for dashboard aggregates, < 1.5 s for GIS viewport queries (excluding cold cache).
- **NFR-P2** Copilot first-token < 3 s; full grounded answer p95 < 20 s.
- **NFR-P3** Nightly batch scoring completes < 2 h for 50k active crop cycles.
- **NFR-P4** Frontend: LCP < 2.5 s on mid-tier mobile over 3G for field-officer routes; route-level code splitting mandatory.

### 4.2 Scalability
- **NFR-S1** Support 300 concurrent users at launch; architecture scales horizontally (stateless API, Redis-backed sessions/queues) to 2,000 without redesign.
- **NFR-S2** Data volumes year 1: 50k farmers, 100k fields, 10M weather rows, 5M stock movements — schema and indexes sized accordingly; time-partition weather and audit tables.

### 4.3 Availability & Reliability
- **NFR-A1** 99.5% monthly availability for core API; ML service degradation must not take down CRUD/dashboard (circuit breaker; serve last predictions flagged stale).
- **NFR-A2** RPO ≤ 1 h (PITR), RTO ≤ 4 h; backup restore drilled quarterly.
- **NFR-A3** All background jobs idempotent and retry-safe; DLQ monitored.

### 4.4 Security (detail in security-architecture.md)
- **NFR-SEC1** OWASP Top 10 controls implemented and verified per release.
- **NFR-SEC2** TLS 1.2+ everywhere; secrets in managed secret store, never in code or images; encryption at rest for DB, object storage, and backups.
- **NFR-SEC3** Rate limiting per IP + per user; stricter budgets on auth and AI endpoints.
- **NFR-SEC4** Audit log immutable (append-only, no UPDATE/DELETE grants), retained ≥ 2 years.
- **NFR-SEC5** Farmer PII: column-level access control, masked by default in UI, never in LLM prompts or logs.

### 4.5 Maintainability & Quality
- **NFR-M1** TypeScript `strict` everywhere; no `any` without justification comment.
- **NFR-M2** Test coverage gates: domain + application layers ≥ 85% lines; overall ≥ 70%; CI blocks below gate.
- **NFR-M3** Architectural boundaries enforced by lint rules (dependency-cruiser): domain imports nothing from infrastructure.
- **NFR-M4** Every significant decision recorded as an ADR.

### 4.6 Observability
- **NFR-O1** Structured JSON logs with request ID + user ID correlation; OpenTelemetry traces across web → API → ML → DB.
- **NFR-O2** RED metrics per endpoint; queue depth, job failure, model-latency dashboards; alerting on SLO burn.
- **NFR-O3** AI observability: prompt/completion logging (PII-scrubbed), token cost per feature, groundedness eval metrics.

### 4.7 Usability & Accessibility
- **NFR-U1** WCAG 2.1 AA; keyboard navigable; screen-reader labels on all interactive elements.
- **NFR-U2** Dark and light themes; responsive 360 px → 4K.
- **NFR-U3** Locale-ready (i18n scaffolding, ICU messages); dates/units localized.

### 4.8 Compliance & Data Governance
- **NFR-C1** Farmer data processing complies with applicable data-protection law (consent recorded at registration; right-to-erasure honored via anonymization while preserving statistical aggregates).
- **NFR-C2** Data retention policy per table class documented in the schema; enforced by scheduled jobs.

---

## 5. Traceability

Every FR maps to: PRD module (§4), ≥ 1 user story, API endpoints (api-specification.md), and DB entities (schema.sql). The traceability matrix is maintained as a living artifact in the project tracker; module implementation PRs must reference FR IDs.

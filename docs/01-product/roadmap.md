# Development Roadmap

Delivery is organized into **6 phases**. Each phase ships production-deployable software behind feature flags; nothing waits for a "big bang". Module numbers reference the PRD feature table.

Rationale for ordering: **data foundations before models, models before AI copilot** — ML and RAG are only as good as the data capture built in Phases 1–2, and the copilot's grounded-SQL layer requires stable curated views over that data.

## Delivery status

> Built on the revised stack ([ADR-0001](../adr/0001-python-backend-no-docker.md): Python/FastAPI, Docker-free).

- **Phase 0 — Platform Foundation:** ✅ Complete (IAM, auth+RBAC, admin UI, CI).
- **Phase 1 — Field Data Foundation:** ✅ Complete (farmers, farms/fields, crop cycles, seed catalog, GIS v1).
- **Phase 2 — Operational Intelligence:** ✅ Complete (weather, crop health + outbreak detection, inventory ledger, supply chain, executive dashboard v1). 71 backend tests green.
- **Phase 3 — Predictive Core:** ⏭️ Next (Python ML service: yield, demand, risk).

---

## Phase 0 — Platform Foundation (Weeks 1–4)

**Goal:** A deployable skeleton with enterprise guardrails, so every later feature lands on rails.

| Workstream | Deliverables |
|-----------|--------------|
| Monorepo | pnpm workspaces: `apps/web`, `apps/api`, `apps/ml`, `packages/*`; shared TS config, ESLint, Prettier |
| Backend core | Express app factory, Clean Architecture layering, DI container, error taxonomy, request validation middleware, health/readiness endpoints |
| Database | Supabase project, Prisma baseline migration, PostGIS + pgvector enabled, audit trigger framework, soft-delete convention |
| Auth (Module 2) | JWT + rotating refresh, RBAC schema, permission middleware, audit logging |
| User mgmt (Module 3) | Organizations, departments, roles, users CRUD + admin UI |
| Frontend core | Vite + React + Tailwind + shadcn/ui shell, dark-mode theme, app layout, routing, React Query + API client with token refresh, form kit (RHF + Zod) |
| DevOps | Dockerfiles, docker-compose (dev), GitHub Actions CI (lint, typecheck, test, build), staging deploy |

**Exit criteria:** admin can create an org, roles, and users on staging; CI green; security headers + rate limiting verified.

## Phase 1 — Field Data Foundation (Weeks 5–9)

**Goal:** Capture the ground truth every model depends on. Modules 4, 5, 8, 18 (base map).

- Farmer management: profiles, contacts, history, dedup.
- Farm & field management: PostGIS geometries, soil data, crop cycles, photos (object storage).
- Seed variety catalog: characteristics, regional suitability matrix.
- GIS v1: Leaflet map with farm/field layers, clustering, region filter.
- Notifications v1 (Module 19): in-app real-time (Socket.IO) + email channel, preference model.

**Exit criteria:** field officer can register farmer→farm→field→crop cycle on a phone browser in < 3 min; data visible on map.

## Phase 2 — Operational Intelligence (Weeks 10–15)

**Goal:** Live operational visibility. Modules 6, 7 (capture), 9, 10.

- Weather intelligence: provider integration, scheduled ingestion (BullMQ), per-farm forecasts, historical store, agro-indicators (GDD, rainfall anomaly).
- Crop monitoring: growth-stage tracking, disease reports with photos, disease heat-map layer.
- Inventory: warehouses, lots, append-only stock movements, transfers (UC-06), expiry tracking, threshold alerts.
- Supply chain: vehicles, orders, deliveries, route plans (v1: manual sequencing + distance calc; optimization in Phase 3), tracking states.
- Executive dashboard v1 (Module 1): live KPIs from operational data.

**Exit criteria:** dashboard reflects real operational state end-to-end; disease report → map → alert loop works (UC-03).

## Phase 3 — Predictive Core (Weeks 16–22)

**Goal:** The ML layer. Modules 11, 12, 13, and route optimization.

- Python FastAPI ML service: feature pipeline, model registry, versioned endpoints.
- Yield prediction: XGBoost baseline trained on historical + weather + soil; nightly batch scoring (UC-04); confidence + intervals.
- Demand forecasting: seasonal models per region × variety; 12-month horizon; backtesting harness.
- Risk intelligence: six domain scores with factor decomposition; daily recompute; threshold alerts.
- Route optimization: OR-Tools VRP solver in ML service (capacity + time windows).
- Model evaluation dashboard (internal): MAPE tracking vs. actuals, drift monitoring.

**Exit criteria:** yield/demand MAPE targets met on held-out season; risk board live; predictions carry lineage.

## Phase 4 — AI Layer (Weeks 23–29)

**Goal:** Prescriptive + conversational intelligence. Modules 14, 15, 16, 17.

- Recommendation engine: rule + signal driven, lifecycle tracking, acceptance analytics.
- Document intelligence: upload → chunk → embed (pgvector) → semantic search with RBAC filtering.
- Executive copilot: LangChain orchestration, intent routing, guarded SQL over semantic-layer views, RAG citations, chart generation, conversation memory, refusal policy (UC-05).
- Scenario simulator: template-driven perturbation + re-scoring, saved comparisons (UC-07).

**Exit criteria:** copilot answers the PRD §5.2 benchmark question set with ≥ 95% grounded (cited) answers and 0 fabricated numbers on the eval suite.

## Phase 5 — Delivery Surfaces & Hardening (Weeks 30–34)

**Goal:** Complete the outer loop and reach production gate. Modules 19 (SMS/push), 20, hardening.

- Reporting: PDF/Excel/CSV export, scheduled reports (UC-08), Power BI dataset endpoint.
- Notifications: SMS provider, web push, digest mode, escalation rules.
- GIS v2: weather overlay, route layer, disease heat-map polish.
- Hardening: penetration test + remediation, load testing (PRD §7), DR drill, observability SLOs, accessibility audit (WCAG 2.1 AA).
- Pilot rollout to one region → feedback cycle → general availability.

---

## Cross-Phase Tracks (continuous)

- **Security:** every module ships with its security review (see security-architecture.md checklist).
- **Testing:** unit + integration gates in CI from Phase 0; E2E smoke suite grows per module.
- **Documentation:** ADRs for every significant decision; API docs generated from route schemas.
- **Data migration:** legacy sales/production ETL runs during Phase 2–3 so Phase 3 models have training data — this is the critical path for ML quality.

## Milestone Summary

| Milestone | Week | Gate |
|-----------|------|------|
| M0 Foundation live on staging | 4 | CI green, auth + RBAC verified |
| M1 Field data flowing | 9 | UC-02 in production pilot |
| M2 Operational visibility | 15 | Dashboard v1 with live data |
| M3 Predictions validated | 22 | MAPE targets met |
| M4 AI layer complete | 29 | Copilot eval suite passed |
| M5 GA | 34 | PRD §7 release criteria met |

## Top Risks to the Plan

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Legacy data quality worse than expected | High | Start ETL discovery in Phase 1; data-quality report by Week 8; models degrade gracefully with completeness flags |
| Weather API coverage gaps in target regions | Medium | Evaluate 2 providers in Phase 0 spike (OQ-1); abstract behind provider interface |
| ML accuracy below target on first season | Medium | Ship with confidence bands + "low confidence" UX; backtesting harness from day one; human-in-the-loop review |
| Copilot hallucination risk | Medium | Grounded-SQL allow-list + citation enforcement + eval suite as release gate |
| Scope pressure to skip P0 hardening | High | Release criteria are contractual (PRD §7); phase gates require sign-off |

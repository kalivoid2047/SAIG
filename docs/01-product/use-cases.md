# Use Cases

Detailed use cases for the highest-value flows. Format follows Cockburn's fully-dressed template (abbreviated where flows are trivial).

---

## UC-01: Authenticate User

- **Actors:** Any user (primary), Auth service
- **Preconditions:** User account exists and is active.
- **Trigger:** User submits credentials on `/login`.
- **Main Success Scenario:**
  1. User submits email + password.
  2. System verifies credentials against Argon2id hash.
  3. System issues access JWT (15 min, in memory) + rotating refresh token (httpOnly, Secure, SameSite=Strict cookie, 7 days).
  4. System records login in audit log; client redirects to role-default landing page.
- **Extensions:**
  - 2a. Invalid credentials → generic error (no user-enumeration), failed-attempt counter++.
  - 2b. 5th failure in 15 min → account locked 15 min; security alert emitted.
  - 3a. MFA enabled (future-ready): system requires TOTP before token issuance.
- **Postconditions:** Session established; audit entry exists.

## UC-02: Register Farmer and Farm

- **Actors:** Field Officer (primary)
- **Preconditions:** Officer authenticated with `farmers:create`.
- **Main Success Scenario:**
  1. Officer opens "New Farmer" form; enters profile + contact.
  2. Officer adds farm: name, region, GPS (device location or map pin), size.
  3. Client validates (Zod schema shared with server); submits.
  4. Server re-validates, persists farmer + farm in one transaction, geocodes region assignment from coordinates.
  5. System schedules initial risk-score computation job for the new farmer.
- **Extensions:**
  - 3a. Connectivity failure → submission queued client-side; retried with idempotency key.
  - 4a. Duplicate detection (same national ID / phone) → 409 with link to existing record.
- **Postconditions:** Farmer + farm queryable; appear on GIS map; risk job enqueued.

## UC-03: Report Crop Disease

- **Actors:** Field Officer (primary), Agronomist (secondary), Notification service
- **Main Success Scenario:**
  1. Officer selects farm → active crop cycle → "Report disease".
  2. Enters disease (from catalog or "unknown"), severity (1–5), affected area %, photos.
  3. System persists report, stores photos in object storage, geotags from field polygon centroid.
  4. System updates disease heat-map layer and recomputes regional disease-risk score (async job).
  5. If severity ≥ threshold or regional cluster detected, system emits real-time alert + email to subscribed agronomists.
- **Extensions:**
  - 4a. Cluster detection: ≥ 3 reports, same disease, ≤ 10 km radius, ≤ 7 days → escalate to outbreak candidate; create high-urgency recommendation.
- **Postconditions:** Report visible on map and in crop-intelligence feed; risk pipeline informed.

## UC-04: Generate Yield Prediction

- **Actors:** Scheduler / Production Manager (primary), ML service
- **Preconditions:** Crop cycle active; model version deployed.
- **Main Success Scenario:**
  1. Nightly job (or manual trigger) collects features per active crop cycle: variety traits, soil metrics, weather aggregates (rolling 30/60/90-day), historical yields, practices.
  2. API service calls ML service `POST /predict/yield` with feature batch.
  3. ML service returns predicted yield/ha, 80% prediction interval, confidence score, model version.
  4. API persists prediction rows (immutable, versioned); dashboard and farm views update.
  5. If prediction deviates > 20% from target, recommendation engine evaluates mitigation rules.
- **Extensions:**
  - 2a. ML service unavailable → job retries with exponential backoff; alert to ops after 3 failures; last valid prediction remains flagged "stale".
  - 3a. Feature completeness below threshold → prediction stored with `low_confidence` flag and excluded from executive aggregates.
- **Postconditions:** Prediction persisted with full lineage (inputs snapshot + model version).

## UC-05: Ask the Executive Copilot

- **Actors:** Executive (primary), Copilot orchestrator, OpenAI API
- **Main Success Scenario:**
  1. Executive types a natural-language question.
  2. Orchestrator classifies intent: data query / document question / forecast / simulation / out-of-scope.
  3. For data queries: LLM generates SQL against a **read-only semantic layer** (curated views, no raw tables); SQL is validated (allow-listed views, SELECT-only, row limits) then executed under a restricted DB role.
  4. Results + retrieved document chunks are composed into a grounded answer with citations; quantitative answers include a chart spec rendered client-side.
  5. Conversation turn is stored (memory); tokens/latency metered.
- **Extensions:**
  - 3a. Generated SQL fails validation → one repair attempt with error feedback → else copilot answers "cannot ground this".
  - 2a. Out-of-scope / PII-seeking question → polite refusal with explanation; logged.
- **Postconditions:** Answer with citations stored in conversation history; audit trail of executed SQL.

## UC-06: Transfer Stock Between Warehouses

- **Actors:** Warehouse Manager (primary)
- **Main Success Scenario:**
  1. Manager creates transfer: source, destination, variety, lot, quantity.
  2. System validates availability with `SELECT ... FOR UPDATE` on source stock; creates transfer in `pending`.
  3. On dispatch confirmation, system writes paired stock movements (out/in-transit) atomically.
  4. On receipt confirmation at destination, movement completes; both warehouse balances reflect it.
- **Extensions:**
  - 2a. Insufficient stock → 422 with current availability; no partial writes.
  - 4a. Receipt discrepancy (short delivery) → variance record created; alert to both managers.
- **Postconditions:** Balances consistent; movement history immutable; low-stock re-evaluated.

## UC-07: Run a What-If Scenario

- **Actors:** Strategic Planner (primary), ML service
- **Main Success Scenario:**
  1. Planner picks a template ("rainfall change", "demand shock", "production delay", "disease outbreak") and sets parameters (region, magnitude, horizon).
  2. System snapshots baseline forecasts, applies parameter perturbations to feature vectors, calls ML service for re-scored forecasts.
  3. System computes deltas (yield, demand, stock coverage, revenue) and renders side-by-side vs. baseline.
  4. Planner saves scenario with name/notes; can share to executives.
- **Postconditions:** Scenario immutable snapshot stored; comparable and exportable.

## UC-08: Generate & Deliver Scheduled Report

- **Actors:** Scheduler (primary), Reporting service
- **Main Success Scenario:**
  1. Cron job fires per report subscription (e.g., monthly board pack).
  2. Worker composes report from materialized views; renders PDF (and/or Excel).
  3. Artifact stored in object storage with retention policy; email dispatched with secure signed link.
- **Extensions:** 2a. Render failure → retry ×3 → ops alert; subscription marked errored, visible in admin.

---

### Use-Case ↔ Module Traceability

| Use case | Modules touched |
|----------|-----------------|
| UC-01 | 2 |
| UC-02 | 4, 5, 18, 13 |
| UC-03 | 7, 13, 14, 18, 19 |
| UC-04 | 12, 6, 5, 14 |
| UC-05 | 15, 16, 11, 12 |
| UC-06 | 9, 19 |
| UC-07 | 17, 11, 12 |
| UC-08 | 20, 19 |

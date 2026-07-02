# User Stories

Format: `US-<module>-<n>` · As a `<persona>`, I want `<capability>`, so that `<outcome>`. Each story lists acceptance criteria (AC) in Given/When/Then shorthand. Priorities inherit from PRD §4 unless stated.

---

## Authentication & Access (Module 2–3)

**US-AUTH-1** — As any user, I want to sign in with email + password and receive a session that silently refreshes, so that I stay productive without re-authenticating hourly.
- AC1: Given valid credentials, when I sign in, then I receive a 15-min access token and an httpOnly rotating refresh cookie.
- AC2: Given an expired access token and valid refresh cookie, when any API call fails with 401, then the client refreshes transparently and retries once.
- AC3: Given 5 failed attempts in 15 minutes, then the account is temporarily locked and the event is audit-logged.

**US-AUTH-2** — As an administrator, I want to assign roles with granular permissions, so that users see only what their job requires.
- AC1: Permissions follow `resource:action` (e.g., `farmers:read`, `inventory:transfer`); roles are permission bundles; users may hold multiple roles.
- AC2: Given a user without `farmers:read`, when they request farmer data, then the API returns 403 and the UI never rendered the navigation entry.

**US-AUTH-3** — As a security officer, I want every sensitive action audit-logged (who, what, when, before/after), so that we can investigate incidents and pass compliance audits.

## Farmer & Farm Management (Modules 4–5)

**US-FARM-1** — As a field officer, I want to register a farmer with profile, contact, and farm GPS location in under 2 minutes, so that field visits stay efficient.
- AC1: Form validates on-device (Zod) before submit; server re-validates.
- AC2: GPS can be captured from device location or map pin-drop.
- AC3: If the request fails due to connectivity, the submission is queued and retried.

**US-FARM-2** — As an agronomist, I want each farm to hold fields with boundaries, soil data, and crop cycles, so that predictions have accurate inputs.
- AC1: Field boundaries stored as PostGIS polygons; area auto-computed in hectares.
- AC2: A crop cycle records variety, planting date, expected harvest, practices, and status.

**US-FARM-3** — As a production manager, I want each farmer to carry a risk score with contributing factors, so that I can prioritize support visits.

## Weather & Crop Intelligence (Modules 6–7)

**US-WX-1** — As an agronomist, I want 14-day weather forecasts and historical trends per farm location, so that I can time planting and treatment.
- AC1: Forecasts refresh at least every 6 h via background jobs; staleness indicator shown.

**US-WX-2** — As a strategic planner, I want climate-risk analysis (drought, flood, heat stress) per region with severity and probability, so that we can act ≥ 14 days ahead.

**US-CROP-1** — As a field officer, I want to submit disease reports with photos and severity, so that outbreaks are detected early.
- AC1: Report auto-geotags from farm; appears on the disease heat-map within 1 minute.
- AC2: A confirmed report above severity threshold triggers alerts to subscribed agronomists.

**US-CROP-2** — As a production manager, I want yield predictions per crop cycle with confidence, so that I can commit volumes to buyers responsibly.

## Inventory & Supply Chain (Modules 9–10)

**US-INV-1** — As a warehouse manager, I want live stock by warehouse × seed variety × lot with expiry dates, so that FEFO dispatch is possible.
- AC1: Stock movements are append-only; current stock is a derived, consistent view.
- AC2: Stock never goes negative — a transfer/dispatch exceeding availability is rejected atomically.

**US-INV-2** — As a warehouse manager, I want low-stock and near-expiry alerts against forecast demand (not static thresholds), so that alerts are meaningful.

**US-SC-1** — As a supply chain manager, I want optimized delivery routes given orders, vehicles, and warehouse origins, so that cost-per-delivery falls.
- AC1: Route plan shows stops in sequence, distance, ETA per stop; is editable before dispatch.

**US-SC-2** — As a sales lead, I want delivery tracking status per order (pending → in-transit → delivered/failed), so that I can inform customers.

## Forecasting, Risk & Recommendations (Modules 11–14)

**US-FC-1** — As a sales lead, I want 12-month demand forecasts by region and variety with seasonal decomposition, so that regional targets are evidence-based.

**US-RISK-1** — As an executive, I want a unified risk board (6 domains, 0–100 scores, trend arrows, contributing factors), so that I see the risk posture at a glance.
- AC1: Scores recompute daily; any score crossing a threshold emits a real-time alert.

**US-REC-1** — As a production manager, I want recommendations that state rationale, expected impact, urgency, and evidence links, so that I can accept or dismiss with accountability.
- AC1: Accept/dismiss is recorded with user + timestamp; acceptance rate is reportable.

## AI Copilot & Documents (Modules 15–16)

**US-AI-1** — As an executive, I want to ask "How does projected maize seed demand in the Eastern region compare to our current stock?" and get an answer with a chart and sources, so that I skip the analyst queue.
- AC1: Answer cites the data sources used; numbers are reproducible from cited views.
- AC2: If the question can't be grounded, the copilot says so and suggests what data would be needed.

**US-DOC-1** — As a strategic planner, I want to upload research PDFs and query them semantically, so that institutional knowledge is searchable.
- AC1: Uploaded docs are chunked, embedded, and searchable within 5 minutes; access respects RBAC.

## Scenario Simulation (Module 17)

**US-SIM-1** — As a strategic planner, I want to simulate "rainfall −30% in region X next season" and see projected yield, demand, inventory, and revenue deltas, so that contingency plans are quantified.
- AC1: Simulations are saved, named, comparable side-by-side, and exportable.

## GIS, Notifications, Reporting (Modules 18–20)

**US-GIS-1** — As an agronomist, I want a map with toggleable layers (farms, disease heat, weather, warehouses, routes), so that spatial patterns become obvious.

**US-NOTIF-1** — As any user, I want to choose channels (in-app, email, SMS) per alert category, so that critical alerts reach me and noise doesn't.

**US-RPT-1** — As an executive, I want a scheduled monthly PDF board report auto-emailed, so that reporting is zero-effort.

---

### Story Map Summary

| Epic | Stories | P0 | P1 | P2 |
|------|---------|----|----|----|
| Access & Governance | US-AUTH-1..3 | 3 | – | – |
| Field Data Foundation | US-FARM-1..3 | 3 | – | – |
| Environmental Intelligence | US-WX-1..2, US-CROP-1..2 | 1 | 3 | – |
| Stock & Logistics | US-INV-1..2, US-SC-1..2 | 2 | 2 | – |
| Predictive Core | US-FC-1, US-RISK-1, US-REC-1 | – | 3 | – |
| AI Layer | US-AI-1, US-DOC-1, US-SIM-1 | – | 1 | 2 |
| Delivery Surfaces | US-GIS-1, US-NOTIF-1, US-RPT-1 | 1 | 1 | 1 |

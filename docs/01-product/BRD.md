# Business Requirements Document (BRD)

**Project:** SeedCo Agro Intelligence Grid (SAIG)
**Version:** 1.0.0 · **Owner:** Product Management · **Status:** Draft for approval

---

## 1. Executive Summary

SeedCo operates a seed production and distribution business exposed to compounding uncertainty: climate variability, disease outbreaks, volatile demand, and fragmented supply chains. Today, decision-critical data lives in disconnected spreadsheets, field reports, and institutional memory. Decisions are reactive and lag events by weeks.

SAIG is an enterprise intelligence platform that centralizes agricultural data and converts it into **predictive, prescriptive intelligence**. It answers four questions at every level of the business:

1. **What is happening?** — live operational visibility (production, inventory, field conditions)
2. **Why is it happening?** — diagnostic analytics correlating weather, soil, disease, and market signals
3. **What will happen?** — ML forecasts for yield, demand, and risk with confidence scores
4. **What should we do?** — AI-generated recommendations, scenario simulation, and an executive copilot

## 2. Business Problem

| # | Problem | Business Impact |
|---|---------|-----------------|
| BP-1 | Yield outcomes are unknown until harvest | Over/under-commitment to buyers; contract penalties |
| BP-2 | Seed demand is estimated by intuition | Stockouts in high-demand regions; write-offs of expired stock elsewhere |
| BP-3 | Climate risk is assessed after damage occurs | Uninsured losses; late replanting decisions |
| BP-4 | Disease outbreaks spread before detection | Multi-region crop loss; reputational damage with growers |
| BP-5 | Inventory and logistics are managed in silos | Excess transport cost; delayed deliveries in planting windows |
| BP-6 | Executives lack a single source of truth | Slow, inconsistent strategic decisions |

## 3. Business Objectives & Success Metrics

| ID | Objective | KPI | Target (Year 1) |
|----|-----------|-----|-----------------|
| BO-1 | Improve yield forecast accuracy | MAPE of yield prediction vs. actual | ≤ 15% |
| BO-2 | Reduce seed stockouts | Stockout incidents per season | −40% |
| BO-3 | Reduce expired/written-off inventory | Write-off value | −25% |
| BO-4 | Earlier risk detection | Lead time from risk signal to alert | ≥ 14 days pre-event |
| BO-5 | Faster executive decisions | Time from question to data-backed answer | Minutes (via copilot) vs. days |
| BO-6 | Centralize agricultural data | % of operational data in SAIG | ≥ 90% |
| BO-7 | Distribution efficiency | Cost per ton-km; on-time delivery rate | −10% cost; ≥ 95% on-time |

## 4. Scope

### In Scope (Phase 1 Program)
Executive dashboard; authentication & RBAC; user/org management; farmer & farm management; weather intelligence; crop intelligence; seed variety catalog; inventory; supply chain intelligence; demand forecasting; yield prediction; risk intelligence; recommendation engine; AI executive copilot; document intelligence (RAG); scenario simulator; GIS; notifications; reporting.

### Out of Scope
- Financial accounting / ERP replacement (SAIG integrates, does not replace)
- Payroll and HR
- E-commerce / direct sales portal for farmers
- IoT sensor hardware procurement (platform is sensor-*ready* via ingestion APIs)
- Mobile native apps (responsive web first; native apps are a future program)

## 5. Stakeholders

| Stakeholder | Role in Project | Primary Interest |
|-------------|----------------|------------------|
| CEO / Executive Board | Sponsor | Strategic visibility, ROI |
| Head of Production | Business owner | Yield forecasts, crop health |
| Head of Supply Chain | Business owner | Inventory, distribution, routing |
| Head of Sales | Business owner | Demand forecasts, regional trends |
| Agronomy Team | Daily users | Field data, disease reports, recommendations |
| Field Officers | Data producers | Simple mobile-friendly data capture |
| IT / Security | Governance | Compliance, data protection, integration |
| Strategic Planning | Analysts | Scenario simulation, reporting |

## 6. Business Constraints

- **BC-1** Cloud budget must support phased rollout (start small, scale with adoption).
- **BC-2** Field officers operate in low-connectivity regions → the web app must be tolerant of intermittent connectivity for data capture (retry queues, optimistic UI).
- **BC-3** Farmer PII is subject to data-protection regulation → encryption, access control, and audit trails are mandatory.
- **BC-4** AI outputs influence financial decisions → every prediction must carry a confidence score and be auditable; the copilot must ground answers in retrievable data (no unverifiable claims).
- **BC-5** Platform must support multiple organizational units (subsidiaries/regions) from day one.

## 7. Business Rules (selected, authoritative list in SRS)

- **BR-1** A farmer belongs to exactly one organization; farms belong to exactly one farmer.
- **BR-2** Stock cannot go negative; transfers require source availability at commit time.
- **BR-3** Every risk score, forecast, and recommendation records the model version and inputs that produced it.
- **BR-4** Only users with explicit permission may view farmer PII; all such access is audit-logged.
- **BR-5** A recommendation must always be traceable to the risk/forecast that triggered it.
- **BR-6** Data is never hard-deleted from core business tables; soft-delete + audit applies.

## 8. Assumptions & Dependencies

- Weather data is sourced from a commercial API (e.g., Open-Meteo/Tomorrow.io/Visual Crossing); historical backfill available.
- Historical sales and production data exists in spreadsheets/legacy systems and will be migrated via a one-time ETL.
- OpenAI API access is approved for use with anonymized/aggregated business data; farmer PII is never sent to external LLMs.
- Supabase PostgreSQL (with PostGIS + pgvector) is the system of record.

## 9. Cost/Benefit Summary

**Costs:** cloud infrastructure (AWS + Supabase + Redis), OpenAI API usage (bounded by budget alerts + caching), weather API subscription, engineering team.
**Benefits:** avoided stockout revenue loss, reduced write-offs, avoided climate/disease losses via early action, logistics savings, and decision velocity. Break-even is projected within the first full crop cycle after go-live, driven primarily by BO-2 and BO-3.

## 10. Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Executive Sponsor | | | |
| Head of Production | | | |
| Head of Supply Chain | | | |
| CTO | | | |

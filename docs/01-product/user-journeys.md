# User Journey Maps

Journeys map persona experience across stages: **Goal → Steps → Touchpoints → Emotions → Pain points removed by SAIG**.

---

## Journey 1: Esther (CEO) — Monday Morning Business Review

**Goal:** Understand business state and top risks in under 10 minutes.

| Stage | Actions | Touchpoint | Before SAIG | With SAIG |
|-------|---------|-----------|-------------|-----------|
| Orient | Opens SAIG, lands on Executive Dashboard | Dashboard | Waits days for analyst decks | KPIs live in 5 seconds |
| Scan risks | Reviews risk board: climate risk 72↑ in Eastern region | Risk board widget | Risks surface after damage | 14-day early warning with factors |
| Drill | Clicks risk → sees affected farms, forecast delta | Risk detail + GIS | Manual cross-referencing | One click, spatial context |
| Question | Asks copilot: "Revenue impact if Eastern yield drops 15%?" | Copilot | Emails analysts, waits | Grounded answer + chart in 20 s |
| Act | Accepts recommendation: pre-position drought-tolerant variety stock | Recommendations | Decisions untracked | Decision logged, impact trackable |

**Emotional arc:** anxiety → clarity → confidence.

---

## Journey 2: Peter (Field Officer) — Farm Visit in a Low-Connectivity Region

**Goal:** Register a new farmer and log a disease observation during one visit.

| Stage | Actions | Touchpoint | Before SAIG | With SAIG |
|-------|---------|-----------|-------------|-----------|
| Prepare | Reviews assigned farms on map, downloads day's data | GIS + farm list | Paper printouts | Route + context on phone |
| Register | Fills farmer form; GPS auto-captured | Farmer form | Paper forms, re-keyed weekly | 2-minute validated form |
| Observe | Photographs leaf spots, files disease report severity 4 | Disease report form | Photo on WhatsApp, lost | Structured, geotagged, tracked |
| Sync | Connectivity drops; submission queues; syncs at next signal | Offline queue | Data lost or delayed days | Automatic retry, idempotent |
| Feedback | Next day sees agronomist confirmed report; treatment recommended | Notifications | Never hears back | Closes the loop → motivation |

**Emotional arc:** friction → flow → being heard.

---

## Journey 3: Sam (Warehouse Manager) — Pre-Season Stock Positioning

**Goal:** Ensure the right varieties are in the right warehouses before planting season.

| Stage | Actions | Touchpoint | Before SAIG | With SAIG |
|-------|---------|-----------|-------------|-----------|
| Assess | Opens inventory dashboard: stock vs. forecast demand coverage per warehouse | Inventory module | Static min/max thresholds | Forecast-aware coverage ratios |
| Alerted | Sees alert: "Warehouse Nakuru covers only 40% of forecast maize demand" | Alert feed | Discovers at stockout | 6 weeks of lead time |
| Plan | Creates transfer from surplus warehouse; system validates availability | Transfer flow | Phone calls + spreadsheets | Atomic, validated, tracked |
| Track | Monitors transfer in-transit; receipt confirmed with variance check | Delivery tracking | Unknown until arrival | Live status, variance flagged |
| Review | Monthly report shows write-offs down, zero stockouts | Reporting | Blame assignment | Evidence of improvement |

---

## Journey 4: Daniel (Agronomist) — Containing a Disease Outbreak

**Goal:** Detect, confirm, and contain a maize leaf blight cluster.

| Stage | Actions | Touchpoint |
|-------|---------|-----------|
| Alerted | Real-time alert: 4 blight reports within 8 km in 5 days → outbreak candidate | Notifications |
| Verify | Opens disease heat-map; inspects report photos and severity trend | GIS + Crop Intelligence |
| Contextualize | Checks weather: humidity spike explains spread; risk score 81 | Weather Intelligence |
| Decide | Reviews AI recommendation: targeted treatment + advisory to 37 farms in buffer zone | Recommendation Engine |
| Execute | Accepts recommendation → notification campaign to affected field officers | Notifications |
| Learn | Post-season: outbreak documented; response time metrics feed next model iteration | Reporting |

---

## Journey 5: Ruth (Sales Lead) — Setting Regional Targets

**Goal:** Set next season's regional sales targets grounded in forecast, not gut feel.

| Stage | Actions | Touchpoint |
|-------|---------|-----------|
| Explore | Opens demand forecast: 12-month view by region × variety with seasonality bands | Demand Forecasting |
| Compare | Runs scenario "demand +20% Eastern (new subsidy program)" | Scenario Simulator |
| Validate | Asks copilot to reconcile forecast vs. current inventory pipeline | Copilot |
| Commit | Exports target sheet (Excel) for the sales team; schedules monthly variance report | Reporting |

---

### Cross-Journey Insights (design implications)

1. **Alert → context → action** is the universal loop: every alert must deep-link into the exact filtered view that explains it, with the relevant recommendation adjacent. (Drives notification payload design and URL state.)
2. **Field officers are the data supply chain.** Their forms get first-class performance and offline budgets; if capture fails, every downstream model degrades.
3. **Trust is earned through traceability.** Executives act on numbers only when confidence + provenance are visible — this is why lineage is a schema-level concern, not a UI afterthought.

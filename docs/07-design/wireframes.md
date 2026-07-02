# Wireframes

Low-fidelity ASCII wireframes for the key screens (desktop 1440; mobile variants noted). Components reference design-system.md. High-fidelity mockups are produced per module during its build phase, using these as the approved structure.

## W1 — Executive Dashboard (landing for executive roles)

```
┌────────┬──────────────────────────────────────────────────────────────────┐
│        │  ⌕ Search (⌘K)      [Org ▾] [Region ▾] [Last 90d ▾]    🔔3  ◉EN │
│  ◧ SAIG├──────────────────────────────────────────────────────────────────┤
│        │  Executive Overview                          as of 09:41 · live  │
│ ▣ Dash │ ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐    │
│ ◈ Farm │ │Prod YTD││Forecast││Inventory││Active  ││On-time ││Active  │    │
│ ⛅ Wthr │ │12.4k t ││Revenue ││ Value  ││ Risks  ││Delivery││Farmers │    │
│ 🌱 Crop │ │▲4% ⎺⎺∿ ││$8.2M ▲ ││$3.1M ▼ ││ 7 ⚠    ││ 96% ▲  ││48,210  │    │
│ ▤ Inv  │ └────────┘└────────┘└────────┘└────────┘└────────┘└────────┘    │
│ ⇶ SC   │ ┌───────────────────────────────┐┌─────────────────────────────┐│
│ ◔ Fcst │ │ Yield Forecast vs Target      ││ Risk Board                  ││
│ ⚠ Risk │ │ [line chart, PI band]         ││ Climate      72 ▲ ████████░ ││
│ ✦ AI   │ │                     [explain✦]││ Disease      41 ▬ █████░░░░ ││
│ ▦ GIS  │ └───────────────────────────────┘│ Supply chain 33 ▼ ████░░░░░ ││
│ ⎙ Rpt  │ ┌───────────────────────────────┐│ Inventory    58 ▲ ██████░░░ ││
│        │ │ Demand Forecast by Region     ││ Production   29 ▬ ███░░░░░░ ││
│ ⚙ Admin│ │ [grouped bars + PI whiskers]  ││ Financial    35 ▬ ████░░░░░ ││
│        │ └───────────────────────────────┘└─────────────────────────────┘│
│        │ ┌───────────────┐┌───────────────┐┌────────────────────────────┐│
│        │ │ Low Stock (10)││ Recommendations││ Live Alerts                ││
│        │ │ Nakuru·MZ-401 ││ ⚡ Pre-position ││ ⚠ Climate risk 72 Eastern  ││
│        │ │ cov 0.4 ⚠     ││ drought-tol.  ││ ▲ Blight cluster Kisumu    ││
│        │ │ …            ││ [Accept][…]   ││ ● Transfer #T-118 received ││
│        │ └───────────────┘└───────────────┘└────────────────────────────┘│
└────────┴──────────────────────────────────────────────────────────────────┘
```
Every KPI/chart/row deep-links to its filtered module view. `[explain ✦]` opens the copilot pre-filled with the widget's context.

## W2 — AI Copilot

```
┌────────┬───────────────────────────────────────────────┬────────────────┐
│ sidebar│  Copilot                                       │ Conversations  │
│        │ ┌───────────────────────────────────────────┐ │ ▸ Q3 planning  │
│        │ │ You: How does projected maize demand in   │ │ ▸ Eastern risk │
│        │ │ Eastern compare to current stock?         │ │ + New          │
│        │ ├───────────────────────────────────────────┤ │                │
│        │ │ ✦ SAIG: Eastern maize demand for the next │ │                │
│        │ │ 90 days is forecast at 412 t (PI 380–450, │ │                │
│        │ │ conf ●●●●○). Current stock across 2 ware- │ │                │
│        │ │ houses is 168 t → coverage 0.41. ⚠        │ │                │
│        │ │ ┌─────────────────────────────┐           │ │                │
│        │ │ │ [bar: demand vs stock/mo]   │           │ │                │
│        │ │ └─────────────────────────────┘           │ │                │
│        │ │ Sources: ⟨demand_outlook⟩ ⟨inventory_     │ │                │
│        │ │ position⟩ · [view SQL]                    │ │                │
│        │ │ Suggested: "Recommend transfer options"   │ │                │
│        │ └───────────────────────────────────────────┘ │                │
│        │ [ Ask about production, demand, risk… ⏎ ]     │                │
└────────┴───────────────────────────────────────────────┴────────────────┘
```
Citations are chips; hover previews the source. Refusals render with an ⓘ style and a "what data would enable this" hint.

## W3 — GIS Map

```
┌────────┬──────────────────────────────────────────────────────────────────┐
│ sidebar│ Map                      Layers: [✓Farms][✓Disease][ Weather]    │
│        │ ┌──────────────────────────────────────────────┐[✓Warehouses]   │
│        │ │        ○42        ◉                          │[ Routes]       │
│        │ │   ○18        ▨▨ heat                         │────────────    │
│        │ │        ⌂            ▨▨▨▨                     │ Legend         │
│        │ │             ○7   ▨▨▨▨▨▨      ⌂              │ ○ farm cluster │
│        │ │    ~~~route~~~~     ▨▨                       │ ⌂ warehouse    │
│        │ │                          ○23                 │ ▨ disease heat │
│        │ └──────────────────────────────────────────────┘                │
│        │ ┌ Selected: Farm "Mwangi A." ─ 3 fields · 4.2 ha · risk 61 ⚠ ─┐ │
│        │ │ Active cycle: MZ-401 growing · pred 3.1 t/ha ●●●○○ [Open →] │ │
│        │ └──────────────────────────────────────────────────────────────┘ │
└────────┴──────────────────────────────────────────────────────────────────┘
```

## W4 — Farmer Registration (field officer, mobile 360px)

```
┌──────────────────────┐   Single column, large touch targets,
│ ← New Farmer    (1/3)│   3-step wizard: Identity → Farm → Review.
│ ──────●──○──○──      │
│ Full name*           │   Offline banner appears when connectivity
│ [________________]   │   drops; submit queues with visible state:
│ National ID          │   "Saved locally — will sync ↻".
│ [________________]   │
│ Phone*               │   GPS step: [Use my location] (primary)
│ [+254 ___________]   │   or map pin-drop fallback; accuracy
│ Region* [Select ▾]   │   radius shown before accept.
│ Cooperative          │
│ [________________]   │   Review step shows dedup warning inline
│ ☑ Consent recorded*  │   if ID/phone matches an existing farmer
│                      │   (link to that record instead of dup).
│ [ Continue → ]       │
└──────────────────────┘
```

## W5 — Inventory: Warehouse Detail

```
┌────────┬──────────────────────────────────────────────────────────────────┐
│ sidebar│ Warehouses ▸ Nakuru (WH-03)          [New Movement][New Transfer]│
│        │ Stock 412 t / cap 600 t ▓▓▓▓▓▓░░░   Coverage 0.41 ⚠   Expiring 3 │
│        │ ┌ Tabs: Stock │ Movements │ Transfers │ Forecast ┐               │
│        │ │ Variety    Lot      Qty(kg)  Expiry     Germ%  Cov.  │         │
│        │ │ MZ-401     L-2401   84,000   2026-11 ⚠  91     0.3⚠ │ FEFO    │
│        │ │ MZ-514     L-2388  120,500   2027-03    94     0.8  │ sorted  │
│        │ │ WH-201     L-2410   67,200   2027-01    89     1.4  │         │
│        │ └──────────────────────────────────────────────────────┘         │
│        │ Forecast tab: projected stock curve vs forecast demand,          │
│        │ with planned receipts/transfers overlaid; alert threshold band.  │
└────────┴──────────────────────────────────────────────────────────────────┘
```

## W6 — Risk Detail (drill-down)

```
┌────────┬──────────────────────────────────────────────────────────────────┐
│ sidebar│ Risk ▸ Climate ▸ Eastern            score 72 ⚠  ▲ +9 (7d)        │
│        │ ┌ Gauge 72 ┐  ┌ Trend 90d line ┐  ┌ Contributing factors ┐      │
│        │ │  ◔ 72    │  │ ∿∿∿∿↗          │  │ Rainfall anomaly −38% ██████│ │
│        │ │  danger  │  │                │  │ Heat-stress days +6  ████  │ │
│        │ └──────────┘  └────────────────┘  │ Soil moisture low    ███   │ │
│        │                                   └────────────────────────────┘ │
│        │ Affected: 1,204 farms · 3 warehouses  [View on map →]            │
│        │ ┌ Linked recommendation ───────────────────────────────────────┐ │
│        │ │ ⚡ HIGH · Pre-position 60t drought-tolerant MZ-514 to Eastern │ │
│        │ │ rationale ▸ · evidence: risk#…, forecast#…  [Accept][Dismiss]│ │
│        │ └──────────────────────────────────────────────────────────────┘ │
└────────┴──────────────────────────────────────────────────────────────────┘
```

## W7 — Scenario Simulator

```
┌────────┬──────────────────────────────────────────────────────────────────┐
│ sidebar│ Scenarios ▸ New                                    [My scenarios]│
│        │ Template: (•) Rainfall change ( ) Demand shock ( ) Delay ( ) Dis.│
│        │ Region [Eastern ▾]  Magnitude [−30% ▾]  Horizon [Next season ▾]  │
│        │ [ Run simulation ]                                               │
│        │ ┌ Results: baseline vs scenario ────────────────────────────────┐│
│        │ │            Baseline   Scenario   Δ                            ││
│        │ │ Yield      3.4 t/ha   2.6 t/ha   −23% ⚠                       ││
│        │ │ Demand     412 t      445 t      +8%                          ││
│        │ │ Coverage   0.78       0.52       −33% ⚠                       ││
│        │ │ Revenue    $2.1M      $1.6M      −24% ⚠                       ││
│        │ │ [waterfall chart of revenue delta]     [Save][Compare][Export]││
│        │ └───────────────────────────────────────────────────────────────┘│
└────────┴──────────────────────────────────────────────────────────────────┘
```

## Screen inventory (full list, structure follows patterns above)

| Area | Screens |
|------|---------|
| Auth | Login, forgot/reset password, (TOTP challenge — MFA-ready) |
| Admin | Users list/detail, roles & permissions matrix editor, departments, audit log explorer, org settings, token budgets |
| Farmers | List (search/filters), detail (profile · farms · history · risk · insights), register wizard |
| Farms | Farm detail (fields map + list), field detail (boundary editor, soil, cycles), crop-cycle detail (timeline, observations, prediction) |
| Crop health | Disease reports list/detail, report form (mobile-first), outbreak view |
| Catalog | Varieties list/detail, suitability matrix |
| Inventory | Warehouses overview, warehouse detail (W5), transfer wizard, movement history |
| Supply chain | Orders, route planner (map + stop list), delivery tracking board |
| Intelligence | Dashboard (W1), demand forecast explorer, yield predictions (region/cycle), risk board + detail (W6), recommendations inbox |
| AI | Copilot (W2), documents library + upload, semantic search, scenarios (W7) |
| Misc | GIS (W3), notifications center + preferences, reports library + subscription editor, profile settings |

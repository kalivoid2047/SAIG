# UI Design System

**Benchmark quality bar:** Linear (interaction polish), Stripe Dashboard (data density with clarity), Azure Portal (enterprise navigation). Built on **Tailwind + shadcn/ui** with a token layer so the theme is centrally owned.

## 1. Brand & color tokens

Dark mode is the primary theme (executive dashboard aesthetic); light mode fully supported. All colors are CSS variables consumed via Tailwind semantic classes — **components never use raw palette values**.

### Semantic tokens (HSL, shadcn convention)

| Token | Dark | Light | Use |
|-------|------|-------|-----|
| `--background` | `222 47% 7%` (#0A0F1E-ish deep navy) | `0 0% 100%` | app canvas |
| `--card` | `222 40% 10%` | `0 0% 100%` | cards, panels |
| `--card-elevated` | `222 36% 13%` | `210 20% 98%` | popovers, modals |
| `--border` | `220 26% 18%` | `214 20% 90%` | hairlines |
| `--foreground` | `210 30% 96%` | `222 47% 11%` | primary text |
| `--muted-foreground` | `215 16% 62%` | `215 16% 44%` | secondary text |
| `--primary` | `152 65% 45%` (agri green) | `152 70% 32%` | actions, active nav |
| `--primary-foreground` | `222 47% 7%` | `0 0% 100%` | text on primary |
| `--accent` | `199 90% 55%` (data cyan) | `199 90% 40%` | links, chart emphasis |
| `--destructive` | `0 72% 55%` | `0 74% 46%` | dangerous actions |
| `--ring` | `152 65% 45%` | same | focus rings |

### Status & data-viz palette

| Token | Value (dark) | Meaning |
|-------|-------------|---------|
| `--success` | `152 65% 45%` | healthy, on-target, delivered |
| `--warning` | `38 92% 55%` | degraded, near-threshold, stale |
| `--danger` | `0 72% 55%` | critical risk, stockout, failed |
| `--info` | `199 90% 55%` | neutral signal |
| `--chart-1..8` | green→cyan→violet→amber sequence, ΔE-spaced, colorblind-checked | Recharts series |

**Risk scale (0–100)** is a fixed gradient: 0–39 `--success`, 40–69 `--warning`, 70–100 `--danger` — identical in charts, maps, badges everywhere (learn once, read everywhere).

## 2. Typography

| Role | Font | Size/line | Weight |
|------|------|-----------|--------|
| UI | Inter (variable) | 14/20 base | 400/500/600 |
| Display (KPIs, page titles) | Inter | 30/36, 24/32 | 600 |
| Numeric (tables, KPIs) | Inter + `font-variant-numeric: tabular-nums` | — | 500 |
| Code/SQL (copilot) | JetBrains Mono | 13/20 | 400 |

Scale: 12, 14 (base), 16, 18, 20, 24, 30, 36. Never below 12 px. Numbers in tables/KPIs always tabular — columns must not wiggle.

## 3. Spacing, radius, elevation, motion

- **Spacing:** Tailwind 4-px grid; card padding 24; section gap 24; page gutter 32 (16 mobile).
- **Radius:** `--radius: 10px` cards/inputs; 6px small controls; full for pills/badges.
- **Elevation (dark theme uses borders + subtle glows, not heavy shadows):** level 1 = border only; level 2 (popover) = border + `0 8px 24px rgb(0 0 0 / 0.4)`; level 3 (modal) = + backdrop blur.
- **Motion (Framer Motion):** page transitions fade+4px rise 180 ms; card hover lift 120 ms; number tickers on KPI change; chart entrance 300 ms stagger; **all gated by `prefers-reduced-motion`**. Nothing bounces — enterprise, not playful.

## 4. Core components (shadcn/ui base + SAIG compositions)

| Component | Composition & behavior |
|-----------|----------------------|
| `AppShell` | Fixed left sidebar (collapsible → icons, 64/240 px), top bar (org/region filter, search ⌘K, alerts bell, user menu), content region with page header slot |
| `KpiCard` | label, big tabular number, delta chip (▲/▼ + % vs. period, semantic color), sparkline, skeleton state |
| `ChartCard` | title, timeframe tabs, Recharts child, empty/loading/error states, export menu (PNG/CSV), "explain" affordance that pre-fills the copilot |
| `DataTable` | TanStack Table: server pagination/sort/filter, column visibility, row selection, sticky header, density toggle, export; URL-synced state |
| `RiskBadge` / `RiskGauge` | score → fixed gradient + trend arrow; gauge for detail views |
| `ConfidenceIndicator` | 0–1 → dots + tooltip explaining model confidence (never a bare decimal) |
| `MapCanvas` | Leaflet wrapper: dark tiles, layer control, cluster styling, drawing tools (field boundaries), viewport-synced data loading |
| `AlertFeedItem` | severity edge-bar, category icon, relative time, deep link, acknowledge action |
| `CopilotPanel` | chat stream (markdown-sanitized), citation chips (hover = source preview), inline `ChartCard`, SQL-view toggle (permitted roles), streaming cursor |
| `RecommendationCard` | urgency chip, rationale expander, evidence links, Accept/Dismiss with confirm + note |
| `FormKit` | RHF+Zod field primitives: labeled input/select/combobox/date/geo-picker; inline errors under fields; sticky submit bar with dirty-state guard |
| `EmptyState` / `ErrorState` | illustration, one-line cause, primary recovery action |
| `StatusChip` | single source for all lifecycle states (cycle, transfer, delivery, recommendation) — one visual language for "status" everywhere |

## 5. Patterns

- **Progressive disclosure:** KPI → click → filtered detail view → row → entity page. Every aggregate is a door, never a dead end.
- **Alert → context:** notifications always deep-link into the exact filtered state that explains them (journey requirement).
- **Stale data honesty:** any widget older than its refresh SLA shows a subtle clock badge with "as of …" — trust through transparency (weather, predictions, MV-backed KPIs).
- **Confidence everywhere:** no prediction renders without its `ConfidenceIndicator`; low-confidence values are visually de-emphasized and excluded from headline KPIs (FR-YLD, SRS).
- **Destructive actions:** typed-confirmation for irreversible ops (write-offs, user deactivation); everything else undo-toast where feasible.
- **Loading:** skeletons matching final layout (no spinners on primary surfaces); optimistic UI only for own-state actions (read/ack).

## 6. Responsive & accessibility

- Breakpoints: 360 (field-officer baseline), 768, 1024, 1440. Sidebar → bottom nav below 768; tables → card lists on mobile for field-officer flows; forms single-column mobile.
- WCAG 2.1 AA: contrast ≥ 4.5:1 verified per token pair in CI (automated check); visible focus rings; full keyboard paths incl. map alternatives (list view parity); ARIA live regions for alert feed and streaming copilot; touch targets ≥ 44 px on field flows.
- i18n-ready: all strings through the message catalog; RTL-safe layout primitives.

## 7. Content voice

Concise, factual, action-first. Errors say what happened + what to do ("Transfer exceeds available stock (1,240 kg available). Reduce quantity."). Numbers formatted with locale separators + explicit units (kg, ha, mm). AI-generated content is always labeled with a subtle sparkle glyph + "AI" tag — humans must always know which text a model wrote.

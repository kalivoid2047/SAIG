# ER Diagram

The full DDL is authoritative: [schema.sql](schema.sql). Diagrams below show relationships per context (a single diagram with 50+ tables is unreadable). Cardinality: `||` one, `o{` many-optional, `|{` many-required.

## 1. Identity & Access (`core`)

```mermaid
erDiagram
    organizations ||--o{ departments : has
    organizations ||--o{ users : employs
    organizations ||--o{ roles : defines
    departments |o--o{ users : groups
    users }o--o{ roles : "user_roles"
    roles }o--o{ permissions : "role_permissions"
    users ||--o{ refresh_tokens : "sessions"
    users ||--o{ password_reset_tokens : ""
    users ||--o{ audit_logs : "actor (nullable)"
    users ||--o{ notifications : receives
    users ||--o{ notification_preferences : configures
```

## 2. Field Operations (`ops`)

```mermaid
erDiagram
    organizations ||--o{ regions : partitions
    organizations ||--o{ farmers : registers
    regions |o--o{ farmers : located_in
    farmers ||--o{ farms : owns
    farmers ||--o{ production_records : "history"
    farms ||--o{ fields : contains
    fields ||--o{ soil_samples : sampled
    fields ||--o{ crop_cycles : hosts
    seed_varieties ||--o{ crop_cycles : planted_as
    seed_varieties }o--o{ regions : "variety_region_suitability"
    crop_cycles ||--o{ growth_observations : monitored
    crop_cycles ||--o{ disease_reports : reported_on
    diseases |o--o{ disease_reports : identifies
    attachments }o--|| farms : "polymorphic"
```

## 3. Inventory & Logistics (`ops`)

```mermaid
erDiagram
    warehouses ||--o{ stock_movements : ledger
    stock_lots ||--o{ stock_movements : of
    seed_varieties ||--o{ stock_lots : batches
    stock_transfers ||--o{ stock_movements : "paired out/in"
    warehouses ||--o{ stock_transfers : "from/to"
    warehouses ||--o{ route_plans : origin
    vehicles |o--o{ route_plans : assigned
    route_plans ||--|{ route_stops : sequenced
    orders ||--|{ order_items : contains
    orders ||--o{ route_stops : visited_as
    orders ||--o{ deliveries : fulfilled_by
    deliveries ||--o{ delivery_events : trail
    regions |o--o{ orders : destination
    regions ||--o{ sales_history : aggregates
    seed_varieties ||--o{ sales_history : ""
```

## 4. Intelligence (`intel`)

```mermaid
erDiagram
    weather_cells ||--o{ weather_observations : daily
    weather_cells ||--o{ weather_forecasts : issued
    regions ||--o{ climate_indicators : scored
    model_versions ||--o{ prediction_runs : executes
    prediction_runs ||--o{ yield_predictions : produces
    prediction_runs ||--o{ demand_forecasts : produces
    feature_snapshots ||--o{ yield_predictions : "lineage"
    crop_cycles ||--o{ yield_predictions : predicted
    regions ||--o{ demand_forecasts : "per region x variety x month"
    regions |o--o{ risk_assessments : scoped
    farmers ||--o{ farmer_risk_scores : scored
    recommendation_rules ||--o{ recommendations : "generated_by (jsonb ref)"
```

## 5. AI (`ai`)

```mermaid
erDiagram
    documents ||--|{ document_chunks : "chunked + embedded (pgvector)"
    users ||--o{ conversations : owns
    conversations ||--|{ messages : contains
    users ||--o{ scenarios : creates
    organizations ||--o{ token_usage_daily : metered
```

## Design decisions worth noting

1. **Stock as ledger, not balance column.** `stock_movements` is append-only; `v_stock_balances` derives truth. Eliminates lost-update bugs, gives free audit history, and the trigger + `FOR UPDATE` pattern makes negative stock impossible (BR-2). Trade-off: balance reads aggregate — mitigated by the indexed view and, if volume demands later, an incrementally-maintained balance table fed by the same ledger.
2. **Predictions immutable with lineage** (`prediction_runs` → `model_versions`, `feature_snapshots`): BR-3 compliance; enables backtesting and "why did the number change" answers.
3. **Weather deduplicated by geohash-5 grid cells**: 50k farms collapse to a few hundred cells → bounded API cost and storage; farm→cell resolution is a spatial join at read time (GIST indexed).
4. **Partitioning:** `audit_logs` (monthly) and `weather_observations` (yearly) are range-partitioned — the two unbounded-growth tables (NFR-S2).
5. **Soft delete via `deleted_at` + partial unique indexes** so uniqueness applies only to live rows (e.g., re-registering a deleted farmer's phone works).
6. **`semantic` schema is a hard security boundary**: copilot's DB role can only see these PII-free views; PII protection is structural, not conventional.

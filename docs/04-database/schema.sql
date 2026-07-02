-- ============================================================================
-- SAIG — SeedCo Agro Intelligence Grid
-- PostgreSQL 15+ · Requires: postgis, pgvector, pgcrypto, pg_trgm
-- Version 1.0.0 — authoritative DDL (Prisma models are generated to match;
-- PostGIS/pgvector/views/triggers live in raw SQL migrations)
--
-- Conventions
--   * snake_case; singular schema prefixes: core, ops, intel, ai, semantic
--   * PKs: uuid DEFAULT gen_random_uuid()
--   * created_at/updated_at on all business tables (updated_at via trigger)
--   * Soft delete: deleted_at TIMESTAMPTZ NULL on core business tables;
--     partial unique indexes exclude soft-deleted rows
--   * Multi-tenancy: organization_id on tenant-scoped tables, always indexed
--   * Money: NUMERIC(14,2); quantities: NUMERIC(12,3) (kg); areas: NUMERIC(10,4) ha
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE SCHEMA IF NOT EXISTS core;      -- identity, access, audit
CREATE SCHEMA IF NOT EXISTS ops;       -- farmers, farms, inventory, logistics
CREATE SCHEMA IF NOT EXISTS intel;     -- weather, predictions, risk, recommendations
CREATE SCHEMA IF NOT EXISTS ai;        -- documents, embeddings, conversations, scenarios
CREATE SCHEMA IF NOT EXISTS semantic;  -- curated read-only views for copilot
CREATE SCHEMA IF NOT EXISTS reporting; -- read-only views for BI / Power BI

-- ---------------------------------------------------------------------------
-- Shared trigger functions
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION core.set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

-- Generic audit trigger: writes before/after images for sensitive tables.
CREATE OR REPLACE FUNCTION core.audit_row_change() RETURNS trigger AS $$
BEGIN
  INSERT INTO core.audit_logs(actor_id, action, entity_schema, entity_table, entity_id, before_data, after_data, request_id)
  VALUES (
    NULLIF(current_setting('app.user_id', true), '')::uuid,
    TG_OP,
    TG_TABLE_SCHEMA,
    TG_TABLE_NAME,
    COALESCE(NEW.id, OLD.id),
    CASE WHEN TG_OP IN ('UPDATE','DELETE') THEN to_jsonb(OLD) END,
    CASE WHEN TG_OP IN ('INSERT','UPDATE') THEN to_jsonb(NEW) END,
    NULLIF(current_setting('app.request_id', true), '')
  );
  RETURN COALESCE(NEW, OLD);
END $$ LANGUAGE plpgsql;

-- ===========================================================================
-- CORE: identity, access, audit
-- ===========================================================================

CREATE TABLE core.organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  slug        TEXT NOT NULL,
  settings    JSONB NOT NULL DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at  TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_organizations_slug ON core.organizations(slug) WHERE deleted_at IS NULL;

CREATE TABLE core.departments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  name            TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ,
  UNIQUE (organization_id, name)
);

CREATE TABLE core.users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  department_id   UUID REFERENCES core.departments(id),
  email           CITEXT NOT NULL,
  password_hash   TEXT NOT NULL,                     -- Argon2id
  full_name       TEXT NOT NULL,
  avatar_url      TEXT,
  locale          TEXT NOT NULL DEFAULT 'en',
  timezone        TEXT NOT NULL DEFAULT 'UTC',
  is_active       BOOLEAN NOT NULL DEFAULT true,
  mfa_secret      TEXT,                              -- encrypted TOTP secret (MFA-ready)
  mfa_enabled     BOOLEAN NOT NULL DEFAULT false,
  failed_attempts SMALLINT NOT NULL DEFAULT 0,
  locked_until    TIMESTAMPTZ,
  last_login_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_users_email ON core.users(email) WHERE deleted_at IS NULL;
CREATE INDEX ix_users_org ON core.users(organization_id);

CREATE TABLE core.roles (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  name            TEXT NOT NULL,
  description     TEXT,
  is_system       BOOLEAN NOT NULL DEFAULT false,   -- seeded roles can't be deleted
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ,
  UNIQUE (organization_id, name)
);

CREATE TABLE core.permissions (
  id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code   TEXT NOT NULL UNIQUE,                       -- 'resource:action', e.g. 'farmers:read_pii'
  label  TEXT NOT NULL
);

CREATE TABLE core.role_permissions (
  role_id       UUID NOT NULL REFERENCES core.roles(id) ON DELETE CASCADE,
  permission_id UUID NOT NULL REFERENCES core.permissions(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE core.user_roles (
  user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
  role_id UUID NOT NULL REFERENCES core.roles(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE core.refresh_tokens (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
  family_id    UUID NOT NULL,                        -- rotation family; reuse detection revokes family
  token_hash   TEXT NOT NULL,                        -- sha256; raw value never stored
  expires_at   TIMESTAMPTZ NOT NULL,
  rotated_at   TIMESTAMPTZ,                          -- non-null = consumed; reuse => breach
  revoked_at   TIMESTAMPTZ,
  ip_address   INET,
  user_agent   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_refresh_tokens_hash ON core.refresh_tokens(token_hash);
CREATE INDEX ix_refresh_tokens_family ON core.refresh_tokens(family_id);

CREATE TABLE core.password_reset_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at    TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only. app_rw role receives INSERT/SELECT only (no UPDATE/DELETE).
CREATE TABLE core.audit_logs (
  id            BIGINT GENERATED ALWAYS AS IDENTITY,
  actor_id      UUID,
  action        TEXT NOT NULL,                       -- INSERT/UPDATE/DELETE or domain action e.g. 'auth.login'
  entity_schema TEXT,
  entity_table  TEXT,
  entity_id     UUID,
  before_data   JSONB,
  after_data    JSONB,
  ip_address    INET,
  request_id    TEXT,
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);                  -- monthly partitions, created by ops job
CREATE INDEX ix_audit_entity ON core.audit_logs(entity_table, entity_id, occurred_at);
CREATE INDEX ix_audit_actor  ON core.audit_logs(actor_id, occurred_at);

-- Transactional outbox for domain events (see AD-2)
CREATE TABLE core.outbox_events (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_type     TEXT NOT NULL,                      -- e.g. 'crop.DiseaseReportCreated'
  event_version  SMALLINT NOT NULL DEFAULT 1,
  aggregate_id   UUID NOT NULL,
  payload        JSONB NOT NULL,
  correlation_id TEXT,
  occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  relayed_at     TIMESTAMPTZ
);
CREATE INDEX ix_outbox_unrelayed ON core.outbox_events(id) WHERE relayed_at IS NULL;

-- ===========================================================================
-- OPS: farmers, farms, catalog, inventory, logistics
-- ===========================================================================

CREATE TABLE ops.regions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  name            TEXT NOT NULL,
  code            TEXT NOT NULL,
  boundary        geometry(MultiPolygon, 4326),
  UNIQUE (organization_id, code)
);
CREATE INDEX ix_regions_boundary ON ops.regions USING GIST (boundary);

CREATE TABLE ops.farmers (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id   UUID NOT NULL REFERENCES core.organizations(id),
  region_id         UUID REFERENCES ops.regions(id),
  full_name         TEXT NOT NULL,
  national_id       TEXT,                            -- PII: column grant restricted
  phone             TEXT,                            -- PII
  email             CITEXT,                          -- PII
  gender            TEXT CHECK (gender IN ('male','female','other','undisclosed')),
  birth_year        SMALLINT CHECK (birth_year BETWEEN 1900 AND 2100),
  cooperative       TEXT,
  consent_given_at  TIMESTAMPTZ,                     -- data-protection consent (NFR-C1)
  registered_by     UUID REFERENCES core.users(id),
  anonymized_at     TIMESTAMPTZ,                     -- right-to-erasure marker
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at        TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_farmers_national_id ON ops.farmers(organization_id, national_id)
  WHERE national_id IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX ux_farmers_phone ON ops.farmers(organization_id, phone)
  WHERE phone IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX ix_farmers_org_region ON ops.farmers(organization_id, region_id);
CREATE INDEX ix_farmers_name_trgm ON ops.farmers USING GIN (full_name gin_trgm_ops);

-- Historical production per farmer-season (pre-SAIG history + closed cycles)
CREATE TABLE ops.production_records (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  farmer_id    UUID NOT NULL REFERENCES ops.farmers(id),
  season       TEXT NOT NULL,                        -- e.g. '2025-long-rains'
  variety_id   UUID,                                 -- FK added after seed_varieties
  area_ha      NUMERIC(10,4) NOT NULL CHECK (area_ha > 0),
  yield_kg     NUMERIC(12,3) NOT NULL CHECK (yield_kg >= 0),
  source       TEXT NOT NULL DEFAULT 'declared' CHECK (source IN ('declared','measured','migrated','cycle_close')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (farmer_id, season, variety_id)
);

CREATE TABLE ops.farms (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  farmer_id       UUID NOT NULL REFERENCES ops.farmers(id),
  region_id       UUID REFERENCES ops.regions(id),
  name            TEXT NOT NULL,
  location        geometry(Point, 4326) NOT NULL,
  total_area_ha   NUMERIC(10,4) CHECK (total_area_ha > 0),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);
CREATE INDEX ix_farms_location ON ops.farms USING GIST (location);
CREATE INDEX ix_farms_farmer ON ops.farms(farmer_id);

CREATE TABLE ops.fields (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  farm_id      UUID NOT NULL REFERENCES ops.farms(id),
  name         TEXT NOT NULL,
  boundary     geometry(Polygon, 4326),
  area_ha      NUMERIC(10,4) NOT NULL CHECK (area_ha > 0),  -- derived from boundary when present
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at   TIMESTAMPTZ
);
CREATE INDEX ix_fields_boundary ON ops.fields USING GIST (boundary);
CREATE INDEX ix_fields_farm ON ops.fields(farm_id);

CREATE TABLE ops.soil_samples (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id       UUID NOT NULL REFERENCES ops.fields(id),
  sampled_at     DATE NOT NULL,
  ph             NUMERIC(4,2) CHECK (ph BETWEEN 0 AND 14),
  nitrogen_ppm   NUMERIC(8,2),
  phosphorus_ppm NUMERIC(8,2),
  potassium_ppm  NUMERIC(8,2),
  organic_matter_pct NUMERIC(5,2) CHECK (organic_matter_pct BETWEEN 0 AND 100),
  texture        TEXT CHECK (texture IN ('sand','loamy_sand','sandy_loam','loam','silt_loam','clay_loam','clay')),
  source         TEXT NOT NULL DEFAULT 'lab' CHECK (source IN ('lab','field_kit','estimate')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_soil_field_date ON ops.soil_samples(field_id, sampled_at DESC);

CREATE TABLE ops.seed_varieties (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id    UUID NOT NULL REFERENCES core.organizations(id),
  crop               TEXT NOT NULL,                  -- maize, wheat, soy…
  name               TEXT NOT NULL,
  code               TEXT NOT NULL,
  maturity_days      SMALLINT CHECK (maturity_days > 0),
  yield_potential_kg_ha NUMERIC(10,2),
  drought_tolerance  SMALLINT CHECK (drought_tolerance BETWEEN 1 AND 5),
  disease_tolerance  SMALLINT CHECK (disease_tolerance BETWEEN 1 AND 5),
  characteristics    JSONB NOT NULL DEFAULT '{}',
  is_active          BOOLEAN NOT NULL DEFAULT true,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at         TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_varieties_code ON ops.seed_varieties(organization_id, code) WHERE deleted_at IS NULL;

ALTER TABLE ops.production_records
  ADD CONSTRAINT fk_production_variety FOREIGN KEY (variety_id) REFERENCES ops.seed_varieties(id);

CREATE TABLE ops.variety_region_suitability (
  variety_id  UUID NOT NULL REFERENCES ops.seed_varieties(id) ON DELETE CASCADE,
  region_id   UUID NOT NULL REFERENCES ops.regions(id) ON DELETE CASCADE,
  score       SMALLINT NOT NULL CHECK (score BETWEEN 1 AND 5),
  rationale   TEXT,
  PRIMARY KEY (variety_id, region_id)
);

CREATE TABLE ops.crop_cycles (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_id            UUID NOT NULL REFERENCES ops.fields(id),
  variety_id          UUID NOT NULL REFERENCES ops.seed_varieties(id),
  season              TEXT NOT NULL,
  status              TEXT NOT NULL DEFAULT 'planned'
                      CHECK (status IN ('planned','planted','growing','harvested','failed')),
  planted_at          DATE,
  expected_harvest_at DATE,
  actual_harvest_at   DATE,
  actual_yield_kg     NUMERIC(12,3) CHECK (actual_yield_kg >= 0),
  practices           JSONB NOT NULL DEFAULT '{}',   -- irrigation, fertilizer regime, tillage
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at          TIMESTAMPTZ,
  CONSTRAINT chk_harvest_data CHECK (actual_yield_kg IS NULL OR status = 'harvested')
);
-- one active cycle per field per season
CREATE UNIQUE INDEX ux_crop_cycles_active ON ops.crop_cycles(field_id, season)
  WHERE status IN ('planned','planted','growing') AND deleted_at IS NULL;
CREATE INDEX ix_crop_cycles_status ON ops.crop_cycles(status) WHERE deleted_at IS NULL;

CREATE TABLE ops.growth_observations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  crop_cycle_id UUID NOT NULL REFERENCES ops.crop_cycles(id),
  observed_by   UUID NOT NULL REFERENCES core.users(id),
  observed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  growth_stage  TEXT NOT NULL CHECK (growth_stage IN
    ('germination','vegetative','flowering','grain_fill','maturity')),
  health_rating SMALLINT NOT NULL CHECK (health_rating BETWEEN 1 AND 5),
  notes         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_growth_obs_cycle ON ops.growth_observations(crop_cycle_id, observed_at DESC);

-- Polymorphic attachments (images/docs on farms, fields, cycles, reports)
CREATE TABLE ops.attachments (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type  TEXT NOT NULL CHECK (entity_type IN ('farm','field','crop_cycle','disease_report','growth_observation')),
  entity_id    UUID NOT NULL,
  storage_key  TEXT NOT NULL UNIQUE,                 -- S3 object key (random)
  mime_type    TEXT NOT NULL,
  size_bytes   INTEGER NOT NULL CHECK (size_bytes > 0),
  captured_gps geometry(Point, 4326),
  uploaded_by  UUID NOT NULL REFERENCES core.users(id),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at   TIMESTAMPTZ
);
CREATE INDEX ix_attachments_entity ON ops.attachments(entity_type, entity_id);

-- --- Crop health -----------------------------------------------------------

CREATE TABLE ops.diseases (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL UNIQUE,
  crop        TEXT NOT NULL,
  pathogen_type TEXT CHECK (pathogen_type IN ('fungal','bacterial','viral','pest','nutritional','unknown')),
  description TEXT,
  treatment_guide TEXT
);

CREATE TABLE ops.disease_reports (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  crop_cycle_id  UUID NOT NULL REFERENCES ops.crop_cycles(id),
  disease_id     UUID REFERENCES ops.diseases(id),   -- NULL = unknown, pending identification
  reported_by    UUID NOT NULL REFERENCES core.users(id),
  severity       SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
  affected_pct   NUMERIC(5,2) NOT NULL CHECK (affected_pct BETWEEN 0 AND 100),
  status         TEXT NOT NULL DEFAULT 'reported'
                 CHECK (status IN ('reported','confirmed','treated','resolved','dismissed')),
  location       geometry(Point, 4326) NOT NULL,     -- field centroid or capture GPS
  notes          TEXT,
  reported_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at     TIMESTAMPTZ
);
CREATE INDEX ix_disease_reports_geo ON ops.disease_reports USING GIST (location);
CREATE INDEX ix_disease_reports_cluster ON ops.disease_reports(disease_id, reported_at); -- outbreak scan

-- --- Inventory --------------------------------------------------------------

CREATE TABLE ops.warehouses (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  region_id       UUID REFERENCES ops.regions(id),
  name            TEXT NOT NULL,
  code            TEXT NOT NULL,
  location        geometry(Point, 4326) NOT NULL,
  capacity_kg     NUMERIC(14,3) CHECK (capacity_kg > 0),
  manager_id      UUID REFERENCES core.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ,
  UNIQUE (organization_id, code)
);
CREATE INDEX ix_warehouses_geo ON ops.warehouses USING GIST (location);

CREATE TABLE ops.stock_lots (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  UUID NOT NULL REFERENCES core.organizations(id),
  variety_id       UUID NOT NULL REFERENCES ops.seed_varieties(id),
  lot_number       TEXT NOT NULL,
  produced_at      DATE NOT NULL,
  expires_at       DATE NOT NULL,
  germination_pct  NUMERIC(5,2) CHECK (germination_pct BETWEEN 0 AND 100),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, lot_number),
  CHECK (expires_at > produced_at)
);

-- Append-only ledger. Balance is derived; negative balances impossible via
-- application-level SELECT ... FOR UPDATE on the (warehouse, lot) pair plus
-- the trigger below as the last line of defense.
CREATE TABLE ops.stock_movements (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  warehouse_id  UUID NOT NULL REFERENCES ops.warehouses(id),
  lot_id        UUID NOT NULL REFERENCES ops.stock_lots(id),
  movement_type TEXT NOT NULL CHECK (movement_type IN
    ('receipt','dispatch','transfer_out','transfer_in','adjustment','write_off')),
  quantity_kg   NUMERIC(12,3) NOT NULL CHECK (quantity_kg <> 0), -- sign = direction
  transfer_id   UUID,                                            -- FK added below
  reference     TEXT,                                            -- order no, PO, etc.
  performed_by  UUID NOT NULL REFERENCES core.users(id),
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_stock_movements_balance ON ops.stock_movements(warehouse_id, lot_id);
CREATE INDEX ix_stock_movements_time ON ops.stock_movements(occurred_at);

CREATE OR REPLACE FUNCTION ops.enforce_non_negative_stock() RETURNS trigger AS $$
DECLARE bal NUMERIC(14,3);
BEGIN
  SELECT COALESCE(SUM(quantity_kg), 0) INTO bal
  FROM ops.stock_movements
  WHERE warehouse_id = NEW.warehouse_id AND lot_id = NEW.lot_id;
  IF bal + NEW.quantity_kg < 0 THEN
    RAISE EXCEPTION 'stock balance would go negative (warehouse %, lot %, balance %, delta %)',
      NEW.warehouse_id, NEW.lot_id, bal, NEW.quantity_kg
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_non_negative BEFORE INSERT ON ops.stock_movements
  FOR EACH ROW WHEN (NEW.quantity_kg < 0) EXECUTE FUNCTION ops.enforce_non_negative_stock();

CREATE TABLE ops.stock_transfers (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id   UUID NOT NULL REFERENCES core.organizations(id),
  from_warehouse_id UUID NOT NULL REFERENCES ops.warehouses(id),
  to_warehouse_id   UUID NOT NULL REFERENCES ops.warehouses(id),
  lot_id            UUID NOT NULL REFERENCES ops.stock_lots(id),
  quantity_kg       NUMERIC(12,3) NOT NULL CHECK (quantity_kg > 0),
  received_kg       NUMERIC(12,3) CHECK (received_kg >= 0),
  status            TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','dispatched','received','cancelled')),
  requested_by      UUID NOT NULL REFERENCES core.users(id),
  dispatched_at     TIMESTAMPTZ,
  received_at       TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (from_warehouse_id <> to_warehouse_id)
);
ALTER TABLE ops.stock_movements
  ADD CONSTRAINT fk_movement_transfer FOREIGN KEY (transfer_id) REFERENCES ops.stock_transfers(id);

-- --- Logistics ---------------------------------------------------------------

CREATE TABLE ops.vehicles (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  registration    TEXT NOT NULL,
  capacity_kg     NUMERIC(12,3) NOT NULL CHECK (capacity_kg > 0),
  status          TEXT NOT NULL DEFAULT 'available'
                  CHECK (status IN ('available','on_route','maintenance','retired')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ,
  UNIQUE (organization_id, registration)
);

CREATE TABLE ops.orders (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  customer_name   TEXT NOT NULL,
  region_id       UUID REFERENCES ops.regions(id),
  destination     geometry(Point, 4326) NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','confirmed','fulfilled','cancelled')),
  requested_date  DATE,
  created_by      UUID NOT NULL REFERENCES core.users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);

CREATE TABLE ops.order_items (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id    UUID NOT NULL REFERENCES ops.orders(id) ON DELETE CASCADE,
  variety_id  UUID NOT NULL REFERENCES ops.seed_varieties(id),
  quantity_kg NUMERIC(12,3) NOT NULL CHECK (quantity_kg > 0),
  unit_price  NUMERIC(14,2) CHECK (unit_price >= 0)
);

CREATE TABLE ops.route_plans (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  origin_warehouse_id UUID NOT NULL REFERENCES ops.warehouses(id),
  vehicle_id      UUID REFERENCES ops.vehicles(id),
  driver_id       UUID REFERENCES core.users(id),
  status          TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','planned','dispatched','completed','cancelled')),
  planned_date    DATE NOT NULL,
  total_distance_km NUMERIC(9,2),
  optimizer_meta  JSONB,                             -- solver stats, savings vs naive
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ops.route_stops (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  route_plan_id UUID NOT NULL REFERENCES ops.route_plans(id) ON DELETE CASCADE,
  order_id      UUID NOT NULL REFERENCES ops.orders(id),
  stop_sequence SMALLINT NOT NULL CHECK (stop_sequence > 0),
  eta           TIMESTAMPTZ,
  UNIQUE (route_plan_id, stop_sequence),
  UNIQUE (route_plan_id, order_id)
);

CREATE TABLE ops.deliveries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id      UUID NOT NULL REFERENCES ops.orders(id),
  route_plan_id UUID REFERENCES ops.route_plans(id),
  status        TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','assigned','in_transit','delivered','failed')),
  delivered_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ops.delivery_events (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  delivery_id  UUID NOT NULL REFERENCES ops.deliveries(id),
  event_type   TEXT NOT NULL,                        -- status_change, location_ping, note
  status       TEXT,
  location     geometry(Point, 4326),
  note         TEXT,
  recorded_by  UUID REFERENCES core.users(id),
  occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_delivery_events ON ops.delivery_events(delivery_id, occurred_at);

-- Historical + ongoing sales (demand model training data)
CREATE TABLE ops.sales_history (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  region_id       UUID NOT NULL REFERENCES ops.regions(id),
  variety_id      UUID NOT NULL REFERENCES ops.seed_varieties(id),
  period_month    DATE NOT NULL,                     -- first day of month
  quantity_kg     NUMERIC(14,3) NOT NULL CHECK (quantity_kg >= 0),
  revenue         NUMERIC(14,2) CHECK (revenue >= 0),
  channel         TEXT NOT NULL DEFAULT 'direct',
  source          TEXT NOT NULL DEFAULT 'live' CHECK (source IN ('live','migrated')),
  UNIQUE (organization_id, region_id, variety_id, period_month, channel)
);

-- ===========================================================================
-- INTEL: weather, ML lineage, predictions, risk, recommendations
-- ===========================================================================

-- Deduplicated ingestion locations (~5km grid cells) to bound API cost
CREATE TABLE intel.weather_cells (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cell_key  TEXT NOT NULL UNIQUE,                    -- geohash-5
  centroid  geometry(Point, 4326) NOT NULL,
  region_id UUID REFERENCES ops.regions(id)
);
CREATE INDEX ix_weather_cells_geo ON intel.weather_cells USING GIST (centroid);

CREATE TABLE intel.weather_observations (
  cell_id        UUID NOT NULL REFERENCES intel.weather_cells(id),
  observed_date  DATE NOT NULL,
  rainfall_mm    NUMERIC(7,2),
  temp_min_c     NUMERIC(5,2),
  temp_max_c     NUMERIC(5,2),
  humidity_pct   NUMERIC(5,2),
  wind_kmh       NUMERIC(6,2),
  source         TEXT NOT NULL,
  ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (cell_id, observed_date)
) PARTITION BY RANGE (observed_date);                -- yearly partitions

CREATE TABLE intel.weather_forecasts (
  cell_id        UUID NOT NULL REFERENCES intel.weather_cells(id),
  forecast_date  DATE NOT NULL,
  issued_at      TIMESTAMPTZ NOT NULL,
  rainfall_mm    NUMERIC(7,2),
  temp_min_c     NUMERIC(5,2),
  temp_max_c     NUMERIC(5,2),
  humidity_pct   NUMERIC(5,2),
  wind_kmh       NUMERIC(6,2),
  source         TEXT NOT NULL,
  PRIMARY KEY (cell_id, forecast_date, issued_at)
);

CREATE TABLE intel.climate_indicators (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  region_id    UUID NOT NULL REFERENCES ops.regions(id),
  indicator    TEXT NOT NULL CHECK (indicator IN ('drought','flood','heat_wave')),
  probability  NUMERIC(4,3) NOT NULL CHECK (probability BETWEEN 0 AND 1),
  severity     SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
  window_start DATE NOT NULL,
  window_end   DATE NOT NULL,
  computed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  details      JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX ix_climate_region ON intel.climate_indicators(region_id, computed_at DESC);

-- --- ML lineage --------------------------------------------------------------

CREATE TABLE intel.model_versions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_name     TEXT NOT NULL,                      -- 'yield_xgb', 'demand_gbm', 'disease_clf'
  version        TEXT NOT NULL,                      -- semver or timestamped
  status         TEXT NOT NULL DEFAULT 'trained'
                 CHECK (status IN ('trained','evaluated','promoted','retired')),
  training_window DATERANGE,
  metrics        JSONB NOT NULL DEFAULT '{}',        -- mape, mae, pi_coverage…
  artifact_key   TEXT NOT NULL,                      -- S3 key
  promoted_at    TIMESTAMPTZ,
  promoted_by    UUID REFERENCES core.users(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_name, version)
);
-- exactly one promoted version per model
CREATE UNIQUE INDEX ux_model_promoted ON intel.model_versions(model_name) WHERE status = 'promoted';

CREATE TABLE intel.feature_snapshots (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type TEXT NOT NULL,                         -- 'crop_cycle', 'region_variety'
  entity_id   UUID NOT NULL,
  features    JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE intel.prediction_runs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_version_id UUID NOT NULL REFERENCES intel.model_versions(id),
  run_type         TEXT NOT NULL CHECK (run_type IN ('scheduled','manual','scenario')),
  triggered_by     UUID REFERENCES core.users(id),
  started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at     TIMESTAMPTZ,
  stats            JSONB NOT NULL DEFAULT '{}'
);

-- Immutable prediction rows (corrections = new runs)
CREATE TABLE intel.yield_predictions (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  prediction_run_id   UUID NOT NULL REFERENCES intel.prediction_runs(id),
  crop_cycle_id       UUID NOT NULL REFERENCES ops.crop_cycles(id),
  feature_snapshot_id UUID NOT NULL REFERENCES intel.feature_snapshots(id),
  predicted_yield_kg_ha NUMERIC(10,2) NOT NULL,
  pi_low_kg_ha        NUMERIC(10,2) NOT NULL,
  pi_high_kg_ha       NUMERIC(10,2) NOT NULL,
  confidence          NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  low_confidence      BOOLEAN NOT NULL DEFAULT false,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (pi_low_kg_ha <= predicted_yield_kg_ha AND predicted_yield_kg_ha <= pi_high_kg_ha)
);
CREATE INDEX ix_yield_pred_cycle ON intel.yield_predictions(crop_cycle_id, created_at DESC);

CREATE TABLE intel.demand_forecasts (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  prediction_run_id   UUID NOT NULL REFERENCES intel.prediction_runs(id),
  organization_id     UUID NOT NULL REFERENCES core.organizations(id),
  region_id           UUID NOT NULL REFERENCES ops.regions(id),
  variety_id          UUID NOT NULL REFERENCES ops.seed_varieties(id),
  period_month        DATE NOT NULL,
  forecast_qty_kg     NUMERIC(14,3) NOT NULL CHECK (forecast_qty_kg >= 0),
  pi_low_kg           NUMERIC(14,3) NOT NULL,
  pi_high_kg          NUMERIC(14,3) NOT NULL,
  confidence          NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  seasonal_component  NUMERIC(10,4),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_demand_fc_lookup ON intel.demand_forecasts(region_id, variety_id, period_month, created_at DESC);

-- --- Risk & recommendations --------------------------------------------------

CREATE TABLE intel.risk_assessments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  region_id       UUID REFERENCES ops.regions(id),   -- NULL = org-level score
  domain          TEXT NOT NULL CHECK (domain IN
    ('climate','disease','supply_chain','inventory','production','financial')),
  score           SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
  factors         JSONB NOT NULL,                    -- [{factor, weight, value, contribution}]
  assessed_date   DATE NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (organization_id, region_id, domain, assessed_date)
);
CREATE INDEX ix_risk_trend ON intel.risk_assessments(organization_id, domain, assessed_date DESC);

CREATE TABLE intel.farmer_risk_scores (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  farmer_id    UUID NOT NULL REFERENCES ops.farmers(id),
  score        SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
  factors      JSONB NOT NULL,
  computed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_farmer_risk_latest ON intel.farmer_risk_scores(farmer_id, computed_at DESC);

CREATE TABLE intel.recommendation_rules (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code        TEXT NOT NULL UNIQUE,
  category    TEXT NOT NULL CHECK (category IN
    ('planting','inventory','distribution','resource','mitigation')),
  definition  JSONB NOT NULL,                        -- declarative condition + template
  version     SMALLINT NOT NULL DEFAULT 1,
  is_active   BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE intel.recommendations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  category        TEXT NOT NULL CHECK (category IN
    ('planting','inventory','distribution','resource','mitigation')),
  title           TEXT NOT NULL,
  rationale       TEXT NOT NULL,                     -- generated narrative
  expected_impact TEXT,
  urgency         TEXT NOT NULL CHECK (urgency IN ('low','medium','high','critical')),
  status          TEXT NOT NULL DEFAULT 'proposed'
                  CHECK (status IN ('proposed','accepted','dismissed','completed')),
  evidence        JSONB NOT NULL DEFAULT '[]',       -- [{type:'risk'|'forecast'|'report', id}]
  generated_by    JSONB NOT NULL,                    -- {rule_id, rule_version} and/or {model, prompt_version}
  decided_by      UUID REFERENCES core.users(id),
  decided_at      TIMESTAMPTZ,
  decision_note   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_recommendations_open ON intel.recommendations(organization_id, status, urgency);

-- ===========================================================================
-- AI: documents, embeddings, conversations, scenarios
-- ===========================================================================

CREATE TABLE ai.documents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  title           TEXT NOT NULL,
  doc_type        TEXT NOT NULL CHECK (doc_type IN ('policy','research','manual','report','other')),
  storage_key     TEXT NOT NULL UNIQUE,
  mime_type       TEXT NOT NULL,
  size_bytes      INTEGER NOT NULL,
  status          TEXT NOT NULL DEFAULT 'processing'
                  CHECK (status IN ('processing','indexed','failed')),
  allowed_roles   UUID[] NOT NULL DEFAULT '{}',      -- empty = org-wide; else role allow-list
  uploaded_by     UUID NOT NULL REFERENCES core.users(id),
  indexed_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);

CREATE TABLE ai.document_chunks (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id      UUID NOT NULL REFERENCES ai.documents(id) ON DELETE CASCADE,
  chunk_index      INTEGER NOT NULL,
  section_path     TEXT,                             -- 'Chapter 3 > Irrigation'
  content          TEXT NOT NULL,
  -- 1536 dims: text-embedding-3-large with dimensions=1536 (API-native reduction).
  -- pgvector HNSW indexes cap at 2000 dims, so native 3072 is not indexable.
  embedding        vector(1536),
  embedding_model  TEXT NOT NULL,
  token_count      INTEGER NOT NULL,
  UNIQUE (document_id, chunk_index)
);
CREATE INDEX ix_chunks_embedding ON ai.document_chunks
  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_chunks_fts ON ai.document_chunks
  USING GIN (to_tsvector('english', content));

CREATE TABLE ai.conversations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  user_id         UUID NOT NULL REFERENCES core.users(id),
  title           TEXT NOT NULL DEFAULT 'New conversation',
  rolling_summary TEXT,                              -- long-term memory
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);
CREATE INDEX ix_conversations_user ON ai.conversations(user_id, updated_at DESC);

CREATE TABLE ai.messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES ai.conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user','assistant','tool','system')),
  content         TEXT NOT NULL,
  citations       JSONB NOT NULL DEFAULT '[]',       -- [{type:'view'|'chunk', ref, label}]
  chart_spec      JSONB,
  executed_sql    TEXT,                              -- audit of guarded-SQL tool
  intent          TEXT,
  prompt_version  TEXT,
  token_usage     JSONB,                             -- {prompt, completion, model}
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_messages_conv ON ai.messages(conversation_id, created_at);

CREATE TABLE ai.token_usage_daily (
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  user_id         UUID NOT NULL REFERENCES core.users(id),
  usage_date      DATE NOT NULL,
  feature         TEXT NOT NULL,                     -- copilot, rag_index, insights
  prompt_tokens   BIGINT NOT NULL DEFAULT 0,
  completion_tokens BIGINT NOT NULL DEFAULT 0,
  cost_usd        NUMERIC(10,4) NOT NULL DEFAULT 0,
  PRIMARY KEY (organization_id, user_id, usage_date, feature)
);

CREATE TABLE ai.scenarios (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  created_by      UUID NOT NULL REFERENCES core.users(id),
  name            TEXT NOT NULL,
  template        TEXT NOT NULL CHECK (template IN
    ('rainfall_change','demand_shock','production_delay','disease_outbreak')),
  parameters      JSONB NOT NULL,                    -- {region_id, magnitude, horizon…}
  baseline        JSONB NOT NULL,                    -- immutable snapshot of baseline forecasts
  results         JSONB,                             -- deltas after simulation
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','completed','failed')),
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);

-- ===========================================================================
-- Notifications & reporting
-- ===========================================================================

CREATE TABLE core.notification_preferences (
  user_id   UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
  category  TEXT NOT NULL,                           -- risk, inventory, outbreak, delivery, system
  channel   TEXT NOT NULL CHECK (channel IN ('in_app','email','sms','push')),
  enabled   BOOLEAN NOT NULL DEFAULT true,
  PRIMARY KEY (user_id, category, channel)
);

CREATE TABLE core.notifications (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES core.users(id),
  category     TEXT NOT NULL,
  severity     TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','warning','critical')),
  title        TEXT NOT NULL,
  body         TEXT,
  deep_link    TEXT,                                 -- SPA route with filters
  channel      TEXT NOT NULL CHECK (channel IN ('in_app','email','sms','push')),
  status       TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending','sent','failed','read','acknowledged')),
  sent_at      TIMESTAMPTZ,
  read_at      TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_notifications_inbox ON core.notifications(user_id, created_at DESC)
  WHERE channel = 'in_app';

CREATE TABLE core.report_subscriptions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES core.organizations(id),
  owner_id        UUID NOT NULL REFERENCES core.users(id),
  report_type     TEXT NOT NULL,                     -- executive_pack, inventory, risk…
  format          TEXT NOT NULL CHECK (format IN ('pdf','xlsx','csv')),
  cron_expression TEXT NOT NULL,
  parameters      JSONB NOT NULL DEFAULT '{}',
  recipients      TEXT[] NOT NULL,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  last_run_at     TIMESTAMPTZ,
  last_status     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.report_artifacts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subscription_id UUID REFERENCES core.report_subscriptions(id),
  report_type     TEXT NOT NULL,
  format          TEXT NOT NULL,
  storage_key     TEXT NOT NULL UNIQUE,
  generated_by    UUID REFERENCES core.users(id),    -- NULL = scheduled
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at      TIMESTAMPTZ
);

-- ===========================================================================
-- Views & materialized views
-- ===========================================================================

-- Current stock balance (canonical read model for inventory)
CREATE VIEW ops.v_stock_balances AS
SELECT sm.warehouse_id,
       sm.lot_id,
       sl.variety_id,
       sl.expires_at,
       SUM(sm.quantity_kg) AS balance_kg
FROM ops.stock_movements sm
JOIN ops.stock_lots sl ON sl.id = sm.lot_id
GROUP BY sm.warehouse_id, sm.lot_id, sl.variety_id, sl.expires_at
HAVING SUM(sm.quantity_kg) <> 0;

-- Latest yield prediction per active crop cycle
CREATE VIEW intel.v_latest_yield_predictions AS
SELECT DISTINCT ON (yp.crop_cycle_id)
       yp.*, mv.model_name, mv.version AS model_version
FROM intel.yield_predictions yp
JOIN intel.prediction_runs pr ON pr.id = yp.prediction_run_id
JOIN intel.model_versions mv ON mv.id = pr.model_version_id
ORDER BY yp.crop_cycle_id, yp.created_at DESC;

-- Dashboard KPIs (refreshed every 15 min by worker; CONCURRENTLY)
CREATE MATERIALIZED VIEW intel.mv_dashboard_kpis AS
SELECT
  f.organization_id,
  COUNT(DISTINCT fr.id) FILTER (WHERE fr.deleted_at IS NULL)              AS active_farmers,
  COUNT(DISTINCT cc.id) FILTER (WHERE cc.status IN ('planted','growing')) AS active_crop_cycles,
  COALESCE(SUM(vlp.predicted_yield_kg_ha * fld.area_ha), 0)              AS projected_production_kg,
  (SELECT COALESCE(SUM(balance_kg),0) FROM ops.v_stock_balances)          AS total_stock_kg,
  (SELECT COUNT(*) FROM intel.risk_assessments ra
     WHERE ra.assessed_date = CURRENT_DATE AND ra.score >= 70)            AS high_risk_count
FROM ops.farmers fr
LEFT JOIN ops.farms f ON f.farmer_id = fr.id
LEFT JOIN ops.fields fld ON fld.farm_id = f.id
LEFT JOIN ops.crop_cycles cc ON cc.field_id = fld.id
LEFT JOIN intel.v_latest_yield_predictions vlp ON vlp.crop_cycle_id = cc.id
GROUP BY f.organization_id;
CREATE UNIQUE INDEX ux_mv_dashboard_kpis ON intel.mv_dashboard_kpis(organization_id);

-- Inventory coverage vs forecast demand (low-stock intelligence, FR-INV-5)
CREATE MATERIALIZED VIEW intel.mv_inventory_coverage AS
WITH demand_next_90 AS (
  SELECT df.region_id, df.variety_id, SUM(df.forecast_qty_kg) AS demand_kg
  FROM intel.demand_forecasts df
  JOIN (SELECT region_id, variety_id, MAX(created_at) AS latest
        FROM intel.demand_forecasts GROUP BY region_id, variety_id) l
    ON l.region_id = df.region_id AND l.variety_id = df.variety_id AND l.latest = df.created_at
  WHERE df.period_month BETWEEN date_trunc('month', CURRENT_DATE)
                            AND date_trunc('month', CURRENT_DATE) + INTERVAL '3 months'
  GROUP BY df.region_id, df.variety_id
)
SELECT w.id AS warehouse_id, w.region_id, sb.variety_id,
       SUM(sb.balance_kg) AS stock_kg,
       d.demand_kg,
       CASE WHEN COALESCE(d.demand_kg,0) = 0 THEN NULL
            ELSE ROUND(SUM(sb.balance_kg) / d.demand_kg, 3) END AS coverage_ratio
FROM ops.v_stock_balances sb
JOIN ops.warehouses w ON w.id = sb.warehouse_id
LEFT JOIN demand_next_90 d ON d.region_id = w.region_id AND d.variety_id = sb.variety_id
GROUP BY w.id, w.region_id, sb.variety_id, d.demand_kg;
CREATE UNIQUE INDEX ux_mv_inventory_coverage ON intel.mv_inventory_coverage(warehouse_id, variety_id);

-- ===========================================================================
-- SEMANTIC layer (copilot surface — PII-free by construction)
-- ===========================================================================

CREATE VIEW semantic.production_summary AS
SELECT r.name AS region, sv.crop, sv.name AS variety, cc.season, cc.status,
       COUNT(*) AS cycle_count, SUM(fld.area_ha) AS total_area_ha,
       AVG(vlp.predicted_yield_kg_ha) AS avg_predicted_yield_kg_ha,
       AVG(vlp.confidence) AS avg_confidence
FROM ops.crop_cycles cc
JOIN ops.fields fld ON fld.id = cc.field_id
JOIN ops.farms fm ON fm.id = fld.farm_id
JOIN ops.regions r ON r.id = fm.region_id
JOIN ops.seed_varieties sv ON sv.id = cc.variety_id
LEFT JOIN intel.v_latest_yield_predictions vlp ON vlp.crop_cycle_id = cc.id
WHERE cc.deleted_at IS NULL
GROUP BY r.name, sv.crop, sv.name, cc.season, cc.status;

CREATE VIEW semantic.demand_outlook AS
SELECT r.name AS region, sv.name AS variety, df.period_month,
       df.forecast_qty_kg, df.pi_low_kg, df.pi_high_kg, df.confidence
FROM intel.demand_forecasts df
JOIN ops.regions r ON r.id = df.region_id
JOIN ops.seed_varieties sv ON sv.id = df.variety_id
JOIN (SELECT region_id, variety_id, MAX(created_at) AS latest
      FROM intel.demand_forecasts GROUP BY region_id, variety_id) l
  ON l.region_id = df.region_id AND l.variety_id = df.variety_id AND l.latest = df.created_at;

CREATE VIEW semantic.inventory_position AS
SELECT w.name AS warehouse, r.name AS region, sv.name AS variety,
       ic.stock_kg, ic.demand_kg AS forecast_demand_90d_kg, ic.coverage_ratio
FROM intel.mv_inventory_coverage ic
JOIN ops.warehouses w ON w.id = ic.warehouse_id
LEFT JOIN ops.regions r ON r.id = ic.region_id
JOIN ops.seed_varieties sv ON sv.id = ic.variety_id;

CREATE VIEW semantic.risk_board AS
SELECT o.name AS organization, r.name AS region, ra.domain, ra.score,
       ra.assessed_date, ra.factors
FROM intel.risk_assessments ra
JOIN core.organizations o ON o.id = ra.organization_id
LEFT JOIN ops.regions r ON r.id = ra.region_id
WHERE ra.assessed_date >= CURRENT_DATE - INTERVAL '90 days';

CREATE VIEW semantic.sales_history AS
SELECT r.name AS region, sv.name AS variety, sh.period_month,
       sh.quantity_kg, sh.revenue, sh.channel
FROM ops.sales_history sh
JOIN ops.regions r ON r.id = sh.region_id
JOIN ops.seed_varieties sv ON sv.id = sh.variety_id;

-- ===========================================================================
-- Roles & grants (executed by migrations role)
-- ===========================================================================
-- app_rw:       full DML on core/ops/intel/ai EXCEPT audit_logs (INSERT/SELECT only)
--               and stock_movements/messages (INSERT/SELECT only — append-only)
-- copilot_ro:   SELECT on semantic.* ONLY; statement_timeout=5s
-- reporting_ro: SELECT on reporting.* and semantic.*
-- migrations:   DDL owner
-- (grant statements templated per environment in the migration pipeline)

-- ===========================================================================
-- updated_at + audit trigger attachment (representative set;
-- migration generator attaches to every table with updated_at)
-- ===========================================================================
DO $$
DECLARE t RECORD;
BEGIN
  FOR t IN
    SELECT table_schema, table_name FROM information_schema.columns
    WHERE column_name = 'updated_at'
      AND table_schema IN ('core','ops','intel','ai')
  LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I.%I
       FOR EACH ROW EXECUTE FUNCTION core.set_updated_at()',
      t.table_name, t.table_schema, t.table_name);
  END LOOP;
END $$;

-- Audit triggers on sensitive tables
CREATE TRIGGER trg_audit_users        AFTER INSERT OR UPDATE OR DELETE ON core.users
  FOR EACH ROW EXECUTE FUNCTION core.audit_row_change();
CREATE TRIGGER trg_audit_roles        AFTER INSERT OR UPDATE OR DELETE ON core.roles
  FOR EACH ROW EXECUTE FUNCTION core.audit_row_change();
CREATE TRIGGER trg_audit_farmers      AFTER INSERT OR UPDATE OR DELETE ON ops.farmers
  FOR EACH ROW EXECUTE FUNCTION core.audit_row_change();
CREATE TRIGGER trg_audit_transfers    AFTER INSERT OR UPDATE OR DELETE ON ops.stock_transfers
  FOR EACH ROW EXECUTE FUNCTION core.audit_row_change();
CREATE TRIGGER trg_audit_recommendations AFTER UPDATE ON intel.recommendations
  FOR EACH ROW EXECUTE FUNCTION core.audit_row_change();

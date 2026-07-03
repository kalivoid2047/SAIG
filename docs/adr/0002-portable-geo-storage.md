# ADR-0002: Portable geospatial storage (deferred PostGIS)

**Status:** Accepted · **Date:** 2026-07-03 · **Context:** Phase 1 (Field Data Foundation)

## Context

The database design (schema.sql) uses PostGIS `geometry` columns for farm locations and field boundaries. Per ADR-0001 the local development database is SQLite (no Docker, no local Postgres install), and a Supabase `DATABASE_URL` is not yet provisioned. PostGIS types would make every Phase 1 module untestable and unrunnable locally.

Phase 1's actual geospatial needs are modest: store a farm point, store a field boundary polygon, compute its area, and render both on a Leaflet map with an optional bounding-box filter. None of that requires a spatial engine.

## Decision

1. **Farm location** = `latitude` / `longitude` numeric columns (WGS84).
2. **Field boundary** = validated **GeoJSON Polygon** in a JSON column; `area_ha` computed server-side from the boundary via spherical shoelace (Chamberlain–Duquette), or entered manually when no boundary is drawn.
3. **Bounding-box queries** (GIS viewport) = plain numeric range predicates on lat/lng — correct and indexable at Phase 1–2 data volumes.
4. **PostGIS adoption is a planned, additive migration** when spatial analytics arrive (disease heat-maps, radius clustering, region containment — Phase 2+): add `geometry` columns computed from the existing lat/lng/GeoJSON data, add GIST indexes, and switch query internals behind the same repository interface. No API contract change.

## Consequences

- Every Phase 1 module develops and tests on SQLite with zero external services; the same code runs unchanged on Supabase/PostgreSQL.
- Spatial precision: spherical area is accurate well under 0.1% for field-sized polygons — beyond agronomic measurement accuracy.
- The outbreak-clustering and heat-map features (Phase 2) are the trigger point for the PostGIS migration; the repository layer is the seam.
- schema.sql remains the North-star design; Alembic migrations are the implementation of record (already the case per ADR-0001).

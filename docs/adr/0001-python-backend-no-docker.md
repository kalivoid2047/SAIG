# ADR-0001: Python backend, Docker-free development and deployment

**Status:** Accepted · **Date:** 2026-07-02 · **Decider:** Project sponsor (stack directive)

## Context

The original architecture (system-architecture.md v1.0.0) specified a Node.js/Express modular monolith plus a separate Python FastAPI ML microservice, with Docker/ECS as the packaging and deployment substrate and Redis/BullMQ for queues. The sponsor has directed that the platform must **not depend on Docker** and must **use Python** as the backend technology.

## Decision

1. **Single Python backend.** The API is a **FastAPI modular monolith** (Python 3.12) that will also host the ML plane (scikit-learn/XGBoost run in-process or as a separately started uvicorn worker later) — the Node/Express tier is removed. This *simplifies* the original AD-1: one backend language, no cross-runtime HTTP hop between API and ML.
2. **No Docker anywhere in the required path.** Local development runs natively (Python venv + uvicorn, Vite dev server). Staging/production run on a VM or PaaS via **systemd + uvicorn workers behind Nginx** (deployment guide to be revised when Phase 5 hardening starts). CI uses GitHub-hosted runners directly — no image builds.
3. **Datastores without containers:**
   - PostgreSQL: **Supabase cloud** for staging/production *and* shared dev. For fully-local development and automated tests, **SQLite** (via SQLAlchemy) is a supported fallback — Phase 0's identity/access schema is deliberately portable. Modules that need PostGIS/pgvector (Phase 1+) require a Supabase/Postgres `DATABASE_URL`; tests for those modules run against a provisioned test database, not containers.
   - Redis/BullMQ are **removed**. Queues and scheduled jobs will use a **PostgreSQL-backed job runner** (e.g. `procrastinate`, which uses LISTEN/NOTIFY) + APScheduler — one less stateful service, aligned with the outbox pattern already in the design (AD-2 stands, the relay target changes).
   - Caching: in-process TTL caches per instance; Postgres for anything shared. Rate limiting: in-memory sliding windows (per instance) + Cloudflare edge rules.
4. **Unchanged:** React/Vite/TS frontend (Node remains a *build-time* tool only), Supabase PostgreSQL as system of record, Clean Architecture/DDD module layout, JWT + rotating refresh auth design, the entire API contract, and the AI architecture (LangChain has a first-class Python SDK — this pivot removes the previous split-brain between Node LangChain and Python ML).

## Consequences

- **Positive:** one backend language and ecosystem; ML and API share code (feature pipelines, schemas); simpler onboarding (no Docker Desktop requirement — relevant on Windows dev machines); fewer moving parts (no Redis); LangChain/pydantic/SQLAlchemy are all native.
- **Negative / accepted trade-offs:** Python async ecosystem replaces the very mature Node middleware set (mitigated: FastAPI is equally mature); horizontal scaling now means "more uvicorn processes/VMs" managed by systemd/PaaS instead of ECS tasks (acceptable at target scale, NFR-S1); in-memory rate limits are per-process (acceptable behind Cloudflare; revisit if instance count grows); Socket.IO is replaced by native WebSockets (`fastapi` + `python-socketio` remains an option).
- **Docs impact:** system-architecture.md, infrastructure.md, ci-cd.md, deployment-guide.md, folder-structure.md and coding-standards.md carry an amendment banner referencing this ADR; full rewrites happen opportunistically as the affected phases begin. The database schema (schema.sql) is unaffected. `packages/contracts` (Zod) is replaced by **pydantic schemas in the backend + generated OpenAPI → generated TS client types** for the frontend (same single-source-of-truth goal, Python-first mechanism).

## Revised tech stack summary

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · pydantic v2 · argon2-cffi · PyJWT |
| Jobs | procrastinate (PG-backed) + APScheduler (from Phase 2) |
| ML | scikit-learn · XGBoost · pandas (in-repo package, same runtime) |
| AI | LangChain (Python) · OpenAI SDK · pgvector |
| Frontend | React · TypeScript · Vite · Tailwind · React Query (unchanged) |
| Database | Supabase PostgreSQL (PostGIS/pgvector); SQLite fallback for local dev/tests of portable modules |
| Deploy | systemd + uvicorn + Nginx on VM/PaaS · GitHub Actions · Cloudflare |

# SAIG — SeedCo Agro Intelligence Grid

AI-powered agricultural intelligence and decision-support platform for SeedCo: yield prediction, demand forecasting, risk intelligence, supply-chain optimization, an AI executive copilot, and GIS-driven field operations.

> **Status:** 🚧 Active build. **Phases 0–2 complete** (foundation, field data, operational intelligence). **Phase 3 (Predictive ML) next.** Built on the revised stack per [ADR-0001](docs/adr/0001-python-backend-no-docker.md) — **Python backend, Docker-free**.

## Delivery status

| Phase | Scope | State |
|-------|-------|-------|
| **0 — Platform Foundation** | Auth (JWT + rotating refresh), RBAC, users/orgs/departments, audit log, admin UI, CI | ✅ Complete |
| **1 — Field Data Foundation** | Farmers (PII-tiered), farms/fields (GeoJSON + area), crop cycles, seed catalog, GIS map | ✅ Complete |
| **2 — Operational Intelligence** | Weather (Open-Meteo), crop health + outbreak detection, inventory ledger, supply chain, executive dashboard | ✅ Complete |
| **3 — Predictive Core** | Python ML service: yield, demand, risk scoring | ⏭️ Next |
| 4 — AI Layer | Recommendations, copilot (RAG), documents, scenarios | Planned |
| 5 — Delivery Surfaces | Reporting, notifications, hardening, GA | Planned |

**81 backend tests passing.** See the [roadmap](docs/01-product/roadmap.md) for the full plan.

## What's built

- **Identity & access** — Argon2id passwords, 15-min access JWTs, rotating refresh tokens with reuse detection, RBAC (`resource:action` permissions) enforced with per-organization scoping, append-only audit log. System roles: Administrator, Viewer, Field Officer, Agronomist, Warehouse Manager, Supply Chain Manager, Driver.
- **Field operations** — farmer registration with consent capture, duplicate detection, and a `farmers:read_pii` masking tier; farms with portable lat/lng geo; fields with GeoJSON boundaries + server-computed area; crop cycles with enforced stage transitions; seed-variety catalog with regional suitability.
- **Operational intelligence** — 14-day weather forecasts + agro-indicators (GDD, rainfall, heat stress) via keyless Open-Meteo; disease reporting with automatic haversine-based outbreak detection; an append-only stock ledger (negative stock impossible) with lots, transfers, and FEFO/expiry; supply chain with vehicles, orders, nearest-neighbour route planning, dispatch and delivery tracking.
- **Executive dashboard** — live cross-module KPIs; a Leaflet map with farm, disease-heatmap, and active-route layers.

## Tech stack

**Frontend** React · TypeScript · Vite · Tailwind · React Query · React Router · Leaflet
**Backend** Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · pydantic v2 · Argon2id · PyJWT · httpx
**Data** Supabase PostgreSQL (PostGIS + pgvector in later phases) — **SQLite fallback for local dev/tests**
**Planned** scikit-learn · XGBoost (Phase 3) · OpenAI · LangChain · RAG (Phase 4)
**Ops** GitHub Actions · Cloudflare — **no Docker required** ([ADR-0001](docs/adr/0001-python-backend-no-docker.md))

## Quick start

**Prerequisites:** Python 3.12+, Node 20+.

```bash
# Backend — apps/api
cd apps/api
python -m venv .venv
.venv\Scripts\activate            # Windows  (Unix: source .venv/bin/activate)
pip install -e ".[dev]"
alembic upgrade head              # creates a local SQLite dev DB by default
python -m saig.scripts.seed --password DevAdmin123!   # org, roles, admin user
python -m saig.scripts.seed_demo  # optional: regions, farmers, weather, stock, routes…
uvicorn saig.main:app --reload --port 8000

# Frontend — apps/web (new terminal, from repo root)
cd apps/web
npm install
npm run dev                       # http://localhost:5173 → proxies /api to :8000
```

Sign in at http://localhost:5173 with **`admin@seedco.example` / `DevAdmin123!`**.

To run against PostgreSQL/Supabase instead of SQLite, set `DATABASE_URL` (see [`.env.example`](.env.example)) to a connection string, e.g. `postgresql+asyncpg://…`.

### Common commands

```bash
# Backend (from apps/api, venv active)
python -m pytest            # 81 tests
python -m ruff check .      # lint

# Frontend (from repo root)
npm run build --workspace apps/web   # strict tsc + vite production build
```

## Project structure

```
SAIG/
├── apps/
│   ├── api/                     # FastAPI modular monolith (Python)
│   │   ├── saig/
│   │   │   ├── shared/          # config, db, security, errors, middleware, geo
│   │   │   ├── modules/         # bounded contexts: iam, fieldops, catalog,
│   │   │   │                    #   weather, crophealth, inventory,
│   │   │   │                    #   supplychain, dashboard
│   │   │   ├── scripts/         # seed, seed_demo
│   │   │   ├── app.py           # app factory + router wiring
│   │   │   └── main.py          # uvicorn entrypoint
│   │   ├── migrations/          # Alembic
│   │   └── tests/               # pytest (httpx + SQLite)
│   └── web/                     # React + Vite SPA
│       └── src/
│           ├── app/             # router, AppShell
│           ├── features/        # mirrors backend modules
│           ├── components/      # shared UI kit
│           └── lib/             # api client (silent refresh), auth, types
├── docs/                        # 27-deliverable engineering doc set + ADRs
└── .github/workflows/           # CI (lint, test, build — Docker-free)
```

Each backend module owns its `models · schemas · repository · service · routes`. Frontend features mirror backend modules one-to-one.

## Documentation

The complete engineering documentation set lives in [`docs/`](docs/00-INDEX.md):

- **Product** — [BRD](docs/01-product/BRD.md) · [PRD](docs/01-product/PRD.md) · [User stories](docs/01-product/user-stories.md) · [Use cases](docs/01-product/use-cases.md) · [Journeys](docs/01-product/user-journeys.md) · [Roadmap](docs/01-product/roadmap.md)
- **Requirements** — [SRS (functional + non-functional)](docs/02-requirements/SRS.md)
- **Architecture** — [System](docs/03-architecture/system-architecture.md) · [Domain model](docs/03-architecture/domain-model.md) · [Folder structure](docs/03-architecture/folder-structure.md) · [AI](docs/03-architecture/ai-architecture.md) · [Security](docs/03-architecture/security-architecture.md) · [Infrastructure](docs/03-architecture/infrastructure.md)
- **Database** — [ER diagrams](docs/04-database/er-diagram.md) · [Full SQL schema](docs/04-database/schema.sql)
- **API** — [REST + WebSocket specification](docs/05-api/api-specification.md)
- **Engineering** — [Coding standards](docs/06-engineering/coding-standards.md) · [Testing strategy](docs/06-engineering/testing-strategy.md) · [CI/CD](docs/06-engineering/ci-cd.md) · [Deployment guide](docs/06-engineering/deployment-guide.md)
- **Design** — [UI design system](docs/07-design/design-system.md) · [Wireframes](docs/07-design/wireframes.md)
- **Decisions** — [ADR-0001: Python backend, Docker-free](docs/adr/0001-python-backend-no-docker.md) · [ADR-0002: Portable geo storage](docs/adr/0002-portable-geo-storage.md)

> Note: the architecture/database docs describe the original Node.js design; where the implementation diverges (Python stack, deferred PostGIS), the ADRs are authoritative. Amendment banners on affected docs point to them.

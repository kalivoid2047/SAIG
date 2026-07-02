# SAIG — SeedCo Agro Intelligence Grid

AI-powered agricultural intelligence and decision-support platform for SeedCo: yield prediction, demand forecasting, risk intelligence, supply-chain optimization, an AI executive copilot, and GIS-driven field operations.

> **Status:** 🚧 Phase 0 (platform foundation) in progress — documentation approved; stack revised per [ADR-0001](docs/adr/0001-python-backend-no-docker.md) (Python backend, Docker-free).

## Documentation

The complete engineering documentation set (27 deliverables) lives in [`docs/`](docs/00-INDEX.md):

- **Product** — [BRD](docs/01-product/BRD.md) · [PRD](docs/01-product/PRD.md) · [User stories](docs/01-product/user-stories.md) · [Use cases](docs/01-product/use-cases.md) · [Journeys](docs/01-product/user-journeys.md) · [Roadmap](docs/01-product/roadmap.md)
- **Requirements** — [SRS (functional + non-functional)](docs/02-requirements/SRS.md)
- **Architecture** — [System](docs/03-architecture/system-architecture.md) · [Domain model](docs/03-architecture/domain-model.md) · [Folder structure](docs/03-architecture/folder-structure.md) · [AI](docs/03-architecture/ai-architecture.md) · [Security](docs/03-architecture/security-architecture.md) · [Infrastructure](docs/03-architecture/infrastructure.md)
- **Database** — [ER diagrams](docs/04-database/er-diagram.md) · [Full SQL schema](docs/04-database/schema.sql)
- **API** — [REST + WebSocket specification](docs/05-api/api-specification.md)
- **Engineering** — [Coding standards](docs/06-engineering/coding-standards.md) · [Testing strategy](docs/06-engineering/testing-strategy.md) · [CI/CD](docs/06-engineering/ci-cd.md) · [Deployment guide](docs/06-engineering/deployment-guide.md)
- **Design** — [UI design system](docs/07-design/design-system.md) · [Wireframes](docs/07-design/wireframes.md)

## Tech stack (summary)

React · TypeScript · Vite · Tailwind — **Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · pydantic v2** — Supabase PostgreSQL (PostGIS + pgvector; SQLite fallback for local dev/tests) — scikit-learn · XGBoost — OpenAI · LangChain · RAG — GitHub Actions · Cloudflare. **No Docker required** ([ADR-0001](docs/adr/0001-python-backend-no-docker.md)).

## Quick start (Phase 0)

```bash
# Backend (Python 3.12+)
cd apps/api
python -m venv .venv && .venv\Scripts\activate    # Windows (use source .venv/bin/activate on Unix)
pip install -e ".[dev]"
alembic upgrade head                               # creates local SQLite dev DB by default
python -m saig.scripts.seed                        # seeds org, roles, admin (prints credentials)
uvicorn saig.main:app --reload --port 8000

# Frontend (Node 20+)
cd apps/web
npm install
npm run dev                                        # http://localhost:5173 → proxies /api to :8000
```

Set `DATABASE_URL` to a Supabase/PostgreSQL connection string to run against Postgres; without it, a local SQLite file is used (fine for Phase 0 modules).

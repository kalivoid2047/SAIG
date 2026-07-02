# Folder Structure

> **⚠ Amended by [ADR-0001](../adr/0001-python-backend-no-docker.md):** `apps/api` is a **Python/FastAPI** package (modules keep the same bounded-context slices with `models/schemas/repository/service/routes` per module); `packages/contracts` is replaced by pydantic schemas + generated OpenAPI → TS client types; workspaces use **npm** instead of pnpm; no `infra/docker`. The tree below reflects the original Node layout — the implemented layout in the repo is authoritative.

Monorepo managed with **pnpm workspaces**. Rationale: shared types/validation between web and api (single source of truth for contracts), atomic cross-cutting PRs, one CI pipeline; ML service lives in the same repo for versioned lockstep with its API consumer but is dependency-isolated (Python).

```
SAIG/
├── package.json                    # workspace root, scripts fan out via pnpm -r / turbo
├── pnpm-workspace.yaml
├── turbo.json                      # task graph: build/test/lint caching
├── docker-compose.yml              # dev: postgres(+postgis,+pgvector), redis, mailpit
├── .github/workflows/              # CI/CD (see ci-cd.md)
├── docs/                           # this documentation tree + ADRs
│   └── adr/
│
├── packages/
│   ├── contracts/                  # ★ single source of truth for API contracts
│   │   └── src/
│   │       ├── <module>/           # per module: zod schemas + inferred TS types
│   │       │   ├── farmer.schemas.ts     # request/response/query schemas
│   │       │   └── farmer.types.ts       # z.infer exports
│   │       └── common/             # pagination, problem+json, ids, enums
│   ├── config/                     # env schema (zod), typed config loader
│   ├── ui/                         # (optional later) shared UI primitives if a 2nd app appears
│   └── tsconfig/                   # shared tsconfig bases
│
├── apps/
│   ├── api/                        # Node.js modular monolith (also runs as worker)
│   │   ├── src/
│   │   │   ├── main.ts             # API entrypoint (http + socket.io)
│   │   │   ├── worker.ts           # Worker entrypoint (BullMQ consumers only)
│   │   │   ├── app.ts              # express app factory (testable)
│   │   │   ├── container.ts        # DI composition root (awilix)
│   │   │   │
│   │   │   ├── modules/            # ★ feature modules = bounded-context slices
│   │   │   │   └── <module>/       # identical internal shape for every module:
│   │   │   │       ├── domain/
│   │   │   │       │   ├── entities/          # aggregate roots, entities, VOs
│   │   │   │       │   ├── events/            # domain events
│   │   │   │       │   ├── services/          # domain services (pure)
│   │   │   │       │   └── ports/             # repository + gateway interfaces
│   │   │   │       ├── application/
│   │   │   │       │   ├── commands/          # write use cases
│   │   │   │       │   ├── queries/           # read use cases (may hit read models)
│   │   │   │       │   ├── handlers/          # domain-event handlers
│   │   │   │       │   └── jobs/              # BullMQ job definitions
│   │   │   │       ├── infrastructure/
│   │   │   │       │   ├── repositories/      # Prisma/PostGIS adapters
│   │   │   │       │   └── gateways/          # external service adapters
│   │   │   │       └── presentation/
│   │   │   │           ├── routes.ts          # express router, zod-validated
│   │   │   │           └── mappers.ts         # domain → contract DTO mapping
│   │   │   │
│   │   │   │   # modules: iam, users, farmers, farms, weather, crops, seeds,
│   │   │   │   #          inventory, logistics, demand, yield, risk,
│   │   │   │   #          recommendations, copilot, documents, scenarios,
│   │   │   │   #          gis, notifications, reporting, dashboard
│   │   │   │
│   │   │   └── shared/             # cross-module kernel (kept deliberately small)
│   │   │       ├── domain/         # base Entity, AggregateRoot, DomainEvent, Result
│   │   │       ├── errors/         # AppError taxonomy → problem+json
│   │   │       ├── middleware/     # auth, rbac, validate, rateLimit, audit, error
│   │   │       ├── database/       # prisma client, tx helper, outbox relay
│   │   │       ├── queue/          # bullmq factories, scheduler, DLQ wiring
│   │   │       ├── realtime/       # socket.io setup (redis adapter, auth)
│   │   │       ├── observability/  # logger (pino), otel, metrics
│   │   │       └── utils/
│   │   ├── prisma/
│   │   │   ├── schema.prisma
│   │   │   └── migrations/         # includes raw SQL for postgis/pgvector/views/triggers
│   │   └── test/                   # integration + e2e (unit tests live beside sources)
│   │
│   ├── web/                        # React SPA
│   │   ├── src/
│   │   │   ├── main.tsx
│   │   │   ├── app/                # providers, router, layouts, error boundaries
│   │   │   ├── features/           # ★ mirrors backend modules 1:1
│   │   │   │   └── <feature>/
│   │   │   │       ├── api/        # react-query hooks (typed by @saig/contracts)
│   │   │   │       ├── components/ # feature components
│   │   │   │       ├── pages/      # route components (lazy-loaded)
│   │   │   │       ├── hooks/
│   │   │   │       └── types.ts
│   │   │   ├── components/         # app-wide: shadcn/ui in components/ui, charts, map, data-table, forms
│   │   │   ├── lib/                # api client (fetch + refresh), socket client, utils
│   │   │   ├── stores/             # minimal client state (zustand): session, ui prefs
│   │   │   └── styles/
│   │   └── test/                   # playwright e2e; vitest units beside sources
│   │
│   └── ml/                         # Python FastAPI microservice
│       ├── pyproject.toml          # uv/poetry managed
│       ├── app/
│       │   ├── main.py             # FastAPI factory
│       │   ├── api/v1/             # predict_yield, forecast_demand, optimize_routes, simulate
│       │   ├── core/               # settings, logging, otel
│       │   ├── features/           # feature engineering pipelines
│       │   ├── models/             # model wrappers (xgboost, sklearn), registry client
│       │   ├── training/           # training + backtesting scripts (offline)
│       │   └── schemas/            # pydantic contracts (mirrors packages/contracts subset)
│       └── tests/
│
└── infra/
    ├── docker/                     # Dockerfiles per app (multi-stage)
    ├── nginx/
    └── terraform/                  # AWS: vpc, ecs, elasticache, s3, secrets, cloudflare
```

## Rules that keep this structure honest

1. **Modules may not import each other's internals.** Cross-module interaction = domain events, or an explicitly exported application-service interface. Enforced with `dependency-cruiser` rules in CI.
2. **`packages/contracts` is the only place request/response shapes are defined.** The API validates against them; the web app infers types from them. A contract change is a visible, reviewable diff in one package.
3. **Domain layer purity:** no Prisma, no Express, no fetch, no env access inside `domain/`. Enforced by lint boundary rules.
4. **`shared/` is a kernel, not a dumping ground.** Anything feature-specific goes in its module; shared code requires two real consumers before promotion.
5. **Frontend features mirror backend modules** so a vertical slice (e.g., "inventory transfer") is two folders with the same name, top to bottom.

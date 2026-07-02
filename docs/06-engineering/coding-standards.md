# Coding Standards

> **⚠ Amended by [ADR-0001](../adr/0001-python-backend-no-docker.md):** §1–2 (TypeScript backend) now apply to the **frontend only**; backend standards are §4 (Python), promoted to primary: ruff + mypy strict, pydantic at boundaries, thin routers, use-case services, repository adapters, SQLAlchemy-only persistence. The layer-boundary, error-taxonomy, logging, and git/PR rules apply unchanged, language-independent.

Enforced by tooling wherever possible (ESLint flat config, Prettier, tsconfig, dependency-cruiser, ruff/mypy for Python). A standard that isn't lint-enforced must be PR-review-enforced; this document is the reviewer's reference.

## 1. TypeScript (api + web + packages)

- `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`. `any` is lint-error; a justified escape uses `// eslint-disable-next-line -- reason` with the reason mandatory.
- **Parse, don't validate twice:** external input crosses the boundary through a Zod schema from `@saig/contracts`; after that, values are typed and trusted. No re-checking deep in the stack.
- **Errors:** domain/application code returns `Result<T, DomainError>` for *expected* failures (validation, conflicts, not-found); `throw` is reserved for bugs and infrastructure faults. The presentation layer maps both to problem+json.
- **Immutability by default:** `readonly` properties, `as const`, no parameter mutation. Arrays/objects copied on transform (`toSorted`, spread).
- **Naming:** `PascalCase` types/classes, `camelCase` values/functions, `SCREAMING_SNAKE` for true constants, file names `kebab-case.ts`; one exported concept per file; suffix by role: `*.schemas.ts`, `*.repository.ts`, `*.usecase.ts`, `*.routes.ts`.
- **Imports:** absolute via workspace aliases (`@saig/contracts`, `@api/shared/...`); no `../../..`; import order lint-enforced (node → external → workspace → relative).
- **No default exports** (except route-level lazy React components where the framework requires it).
- **Async:** no floating promises (lint); every external call has a timeout; `Promise.all` for independent awaits.
- **Comments:** explain *why* and constraints, never *what* the next line does. Public APIs of packages get TSDoc.

## 2. Backend specifics

- **Layer boundaries (lint-enforced by dependency-cruiser):** `domain` imports only `shared/domain`; `application` imports domain; `infrastructure` implements ports; `presentation` calls application only. No module imports another module's internals — cross-module = domain events or exported application interfaces.
- **Controllers are thin:** parse → call use case → map result. Zero business logic in routes.
- **Use cases are verbs:** `RegisterFarmer`, `DispatchTransfer` — one public `execute()`, dependencies injected via constructor (awilix container registers by module).
- **Transactions:** owned by use cases via a `UnitOfWork` port; repositories never begin/commit. Outbox writes happen inside the same transaction as state changes.
- **Raw SQL** (PostGIS/pgvector/analytics) lives only in infrastructure adapters, always parameterized, always typed with an explicit row type + Zod runtime guard in dev/test.
- **Logging:** pino structured; never log PII, tokens, or full request bodies; always include `requestId`; log levels: error (actionable), warn (degradation), info (state changes), debug (dev only).
- **Config:** read once at boot through the validated config object; `process.env` access outside `packages/config` is lint-banned.

## 3. React / frontend specifics

- **Server state = React Query; client state = zustand (session, UI prefs only).** No server data in zustand — one cache, one invalidation story.
- Query keys follow `[feature, entity, params]`; mutations invalidate by prefix; optimistic updates only where UX demands (notifications read-state, form queues).
- **Components:** function components only; props typed explicitly (no `React.FC`); files ≤ ~200 lines — beyond that, extract; hooks extracted when logic exceeds one concern.
- **Forms:** React Hook Form + `zodResolver` with the *same contract schema the API validates* — client and server can't drift.
- **Routing:** route components lazy-loaded (`React.lazy`) per feature; loaders keep data fetching in React Query, not effects. URL is the source of truth for filters (shareable/deep-linkable — journey requirement).
- **Styling:** Tailwind + shadcn/ui tokens only — no hex literals in components (design-system CSS variables); `clsx`/`cva` for variants; no inline `style` except dynamic geometry.
- **Accessibility:** interactive elements are buttons/links (never clickable divs); every input labeled; focus management on dialogs/route changes; `eslint-plugin-jsx-a11y` error-level.
- `dangerouslySetInnerHTML` lint-banned (markdown renderer exempt, sanitizes via rehype-sanitize).

## 4. Python (ml service)

- Python 3.12; `ruff` (lint+format), `mypy --strict`; pydantic v2 models for all I/O.
- FastAPI routers thin; feature engineering/model code pure and unit-testable (no I/O inside transforms); randomness seeded; model wrappers expose `predict(features) -> Prediction` with dataclass outputs.
- Notebooks never ship: exploration is fine, but anything merged is a script/module with tests.

## 5. SQL & migrations

- Migrations are roll-forward-only in prod; every migration reviewed for lock impact (`CREATE INDEX CONCURRENTLY`, batched backfills).
- Never `SELECT *` in application code; explicit column lists.
- New queries against big tables require an `EXPLAIN` check in the PR description when touching `stock_movements`, `weather_observations`, `audit_logs`, or embeddings.

## 6. Git & PR workflow

- Trunk-based: short-lived branches `feat/<module>-<slug>`, `fix/…`, `chore/…` → PR → squash-merge to `main`.
- **Conventional Commits** (`feat(inventory): enforce non-negative stock on dispatch`) — drives changelog + release tags.
- PR template requires: FR IDs covered, test evidence, security checklist delta (security-architecture §9), screenshots for UI.
- PRs ≤ ~400 lines of reviewable diff; larger work is stacked.
- Two approvals for `main`; CI green mandatory; no force-push to `main`.

## 7. Definition of Done (per module — from the project charter)

Business explanation → architecture note → schema/migrations → API + validation → backend + tests → frontend + tests → docs updated → security review checklist → performance notes → deployment notes. A module PR that skips a step doesn't merge.

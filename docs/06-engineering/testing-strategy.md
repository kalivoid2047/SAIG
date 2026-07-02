# Testing Strategy

**Shape:** classic pyramid with two extra layers for this system's risk profile — data-integrity tests (DB invariants) and AI evaluation suites (non-deterministic components need statistical gates, not assertions).

## 1. Layers

| Layer | Tooling | Scope | Runs |
|-------|---------|-------|------|
| Unit — domain | Vitest | entities, VOs, domain services (pure, no I/O) | every PR, <60 s |
| Unit — application | Vitest + in-memory fakes of ports | use cases: happy + failure paths, event emission | every PR |
| Unit — web | Vitest + Testing Library | components, hooks, form validation | every PR |
| Integration — API | Vitest + supertest + **Testcontainers** (postgres+postgis+pgvector, redis) | route → DB round trips, RBAC matrix, transactions, outbox | every PR |
| Integration — ML | pytest | feature pipelines, model wrappers (frozen fixture models), API contracts | every PR |
| DB invariants | SQL test suite via Testcontainers | negative-stock trigger, partial unique indexes, audit trigger coverage, soft-delete visibility | every PR |
| E2E | Playwright | 8 golden journeys (login, farmer registration, disease report→alert, transfer, dashboard, copilot ask, scenario, report) | merge to main + nightly full matrix |
| Contract | generated OpenAPI diff + Zod schema snapshot | breaking-change detection on `packages/contracts` | every PR touching contracts |
| Load | k6 | dashboard, GIS viewport, copilot concurrency (PRD §7 targets) | weekly + pre-release |
| Security | authz matrix test (every route × role → expected status), dependency audit, ZAP baseline scan | every PR / nightly |
| AI evals | golden-question suite (SQL copilot), RAG retrieval precision, faithfulness judge | on prompt/model/semantic-layer change + nightly |

## 2. Policies

- **Coverage gates (CI-blocking):** domain+application ≥ 85% lines/branches; overall ≥ 70%. Coverage is a floor, not a target — review still checks that assertions are meaningful.
- **Test data:** factory functions per aggregate (`makeFarmer(overrides)`) — no shared fixtures mutated across tests; every integration test seeds its own org (tenant isolation doubles as test isolation).
- **No mocking what you own below the port line:** use cases are tested against in-memory port fakes; repositories are tested against a real Postgres (Testcontainers). Mocked Prisma is banned — it tests nothing real.
- **External services** (OpenAI, weather, SMS): recorded/faked via nock-style interceptors; a small nightly "canary" suite hits sandboxes to catch contract drift.
- **Flake policy:** a flaky test is quarantined within 24 h with an issue; two weeks unquarantined-and-unfixed → deleted (a flaky test is worse than no test).
- **Determinism in ML tests:** seeds pinned; model-quality thresholds tested statistically in the backtest harness, not in unit tests.

## 3. AI evaluation gates (release-blocking, from ai-architecture §5)

| Suite | Content | Gate |
|-------|---------|------|
| Copilot SQL golden set | ≥100 NL questions with expected result sets against seeded semantic layer | ≥95% correct/equivalent |
| Groundedness | adversarial set (leading questions, out-of-scope, PII-fishing, injection attempts in docs) | 100% refusal/no-leak on the hard set |
| RAG retrieval | labeled corpus, precision@6 | ≥0.8 |
| Faithfulness | LLM-judge on sampled answers vs. retrieved context | ≥0.9 |

Suites run in CI against pinned model versions; a model upgrade is a PR that must pass them.

## 4. Environments & data

- Integration/E2E run against ephemeral containers — never shared environments (no test-order coupling).
- Staging E2E nightly against anonymized production-shaped data (volume-realistic — catches the pagination/index issues unit tests can't).
- Load tests only against staging with production-scale seeded data.

## 5. Quality metrics watched per release

Defect escape rate (bugs found in prod vs. pre-prod), E2E duration trend (budget: 15 min), flake rate (<1%), coverage trend, AI eval scores trend, p95 latency from k6 vs. NFR-P targets.

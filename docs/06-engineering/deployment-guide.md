# Deployment Guide

> **⚠ Amended by [ADR-0001](../adr/0001-python-backend-no-docker.md):** local dev is now Docker-free — `python -m venv` + uvicorn for the API, `npm run dev` for the web app, SQLite or a Supabase dev project as the database (see the root README quick-start, which is authoritative for Phase 0). Container/ECS instructions below are superseded; production topology is finalized in Phase 5.

Covers: local development, staging/production provisioning, deploy, verify, rollback, and operations runbook pointers. Assumes the CI/CD pipeline (ci-cd.md) is the normal path — manual steps below are for provisioning and break-glass.

## 1. Local development

**Prerequisites:** Node 20 LTS, pnpm 9, Docker Desktop, Python 3.12 + uv.

```bash
git clone git@github.com:seedco/SAIG.git && cd SAIG
pnpm install
cp .env.example .env            # fill: DATABASE_URL, REDIS_URL, OPENAI_API_KEY (optional for core dev)
docker compose up -d            # postgres(+postgis+pgvector), redis, mailpit
pnpm db:migrate                 # prisma migrate dev + raw SQL migrations
pnpm db:seed                    # demo org, roles/permissions, sample data
pnpm dev                        # turbo: api :3000, web :5173, ml :8000 (uvicorn --reload)
```

Verify: `http://localhost:5173` → login with seeded admin (credentials printed by seed) · `GET :3000/health/ready` · `GET :8000/v1/health`. Mailpit UI at `:8025` shows outbound email.

**Feature-flagged externals:** without `OPENAI_API_KEY` the copilot module runs in "disabled" mode (banner in UI); without a weather key the ingestion worker uses the fixture provider. Core modules never require external keys locally.

## 2. Provisioning environments (once per environment)

1. **Supabase:** create project → enable `postgis`, `vector`, `pg_trgm`, `citext`, `pgcrypto` → note pooled (PgBouncer) + direct connection strings (migrations use direct) → configure PITR.
2. **AWS via Terraform:** `cd infra/terraform/envs/<env> && terraform init && terraform apply` — creates VPC, ECS cluster + services, ALB, ElastiCache, S3 buckets, ECR, Secrets Manager entries (placeholders), IAM OIDC roles for GitHub Actions, CloudWatch alarms.
3. **Secrets:** populate Secrets Manager: `DATABASE_URL`, `DATABASE_DIRECT_URL`, `REDIS_URL`, `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` (RS256 pair), `OPENAI_API_KEY`, `WEATHER_API_KEY`, `SES_*`/`TWILIO_*`, `ML_SERVICE_TOKEN`.
4. **Cloudflare:** DNS records, WAF managed rules, TLS full-strict, cache rules for the web bundle, rate-limit rules (coarse outer layer).
5. **Database roles:** run the roles/grants migration (`app_rw`, `copilot_ro`, `reporting_ro`, `migrations`) — see schema.sql §Roles.
6. Bootstrap: run migrations + `pnpm db:seed:system` (system roles/permissions only, no demo data) then create the first admin via the ops CLI (`pnpm ops:create-admin`).

## 3. Normal deploys

- **Staging:** automatic on merge to `main` (deploy-staging.yml). Nothing to do.
- **Production:** create a release (`gh workflow run release.yml`) → review generated changelog → approve the `production` environment gate. Pipeline: signature verification → migrations → rolling deploy → 5-min health gate → smoke tests.

### Pre-deploy checklist (release captain)
1. Staging soak ≥ 24 h with no new Sentry/alarm classes.
2. Migration review: expand-only? lock-safe? (checklist in PR template)
3. AI eval suites green if prompts/models/semantic views changed.
4. On-call aware; deploy window outside batch-scoring hours (avoid 02:00–04:00 UTC).

## 4. Verification (post-deploy)

- `/health/ready` all services; ECS steady state; error rate + p95 latency vs. baseline (dashboards linked in the deploy notification).
- Functional canary: login → dashboard KPIs load → create+read a test entity in a canary org → copilot health question.
- Background: BullMQ dashboard shows workers consuming; outbox relay lag < 30 s; scheduled jobs registered.

## 5. Rollback & break-glass

| Scenario | Action |
|----------|--------|
| Bad deploy (app) | `gh workflow run rollback.yml -f env=production` → previous task definitions; < 5 min |
| Bad migration | Do **not** roll back the DB. Ship a forward fix; expand/contract discipline keeps previous app version compatible if service rollback is also needed |
| Data incident | Supabase PITR restore to side database → targeted repair scripts → never blind full restore over live data |
| Secret compromise | Rotate in Secrets Manager → force new ECS deployment → revoke refresh-token families (`pnpm ops:revoke-sessions --all`) → incident runbook |
| Full region DR | Follow `docs/runbooks/disaster-recovery.md`: restore DB from cross-region dump (RPO ≤ 1 h), `terraform apply` in DR region, repoint Cloudflare. RTO target 4 h — drilled quarterly |

## 6. Routine operations

- **Scaling:** api scales on CPU/ALB requests; worker on queue-depth metric; thresholds in Terraform (`infra/terraform/modules/ecs`).
- **Partitions:** monthly job creates upcoming `audit_logs`/`weather_observations` partitions (worker cron); alarm if next partition missing.
- **Materialized views:** refreshed CONCURRENTLY by worker (15 min KPIs; hourly coverage); staleness metric exported.
- **Model promotion:** `pnpm ops:promote-model --name yield_xgb --version <v>` after backtest gate; records approver; previous version retained for instant rollback.
- **Cost watch:** budget alarms (infra §7); OpenAI spend dashboard; weather API call counter.
- **Backups:** PITR continuous + nightly logical dump to cross-region S3; restore drill quarterly (calendar-owned by DevOps).

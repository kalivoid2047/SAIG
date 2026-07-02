# Infrastructure Architecture

> **⚠ Amended by [ADR-0001](../adr/0001-python-backend-no-docker.md):** Docker/ECS/ElastiCache are removed. Compute = VM or PaaS running uvicorn under systemd behind Nginx; queues/cache = PostgreSQL + in-process. Cloudflare, S3, Secrets Manager, Supabase, and the environment model stand. This document is rewritten in Phase 5 (hardening); until then treat container specifics below as superseded.

## 1. Topology

| Layer | Technology | Choice rationale |
|-------|-----------|------------------|
| Edge | Cloudflare (DNS, CDN, WAF, DDoS) | Static SPA cached at edge; WAF before anything reaches AWS |
| Ingress | ALB + Nginx sidecar config | TLS termination, path routing `/api` + `/socket.io`, request buffering |
| Compute | **ECS Fargate** | Containers without cluster ops; right-sized per service; chosen over EKS (K8s overhead unjustified for 3 services) and EC2 (patching burden) |
| Database | **Supabase managed PostgreSQL** | PostGIS + pgvector managed, PITR built-in, pooling via PgBouncer; keeps DB ops off the team |
| Cache/queue | ElastiCache Redis (single node dev → replicated prod) | Sessions blocklist, rate limits, cache, BullMQ |
| Object storage | S3 (+ lifecycle policies) | images, documents, report artifacts, ML model artifacts |
| Secrets | AWS Secrets Manager | runtime injection into task definitions |
| Observability | CloudWatch + OTel collector → Grafana/Tempo/Loki (or Grafana Cloud) | unified traces/logs/metrics |

## 2. Services (ECS)

| Service | Image | Scaling signal | Notes |
|---------|-------|---------------|-------|
| `api` | apps/api (entry `main.ts`) | CPU + ALB request count | min 2 tasks (AZ spread); Socket.IO via Redis adapter |
| `worker` | apps/api (entry `worker.ts`) | BullMQ queue depth (custom metric) | min 1; burst for nightly scoring |
| `ml` | apps/ml | CPU | private-only; no public route |

One image for api+worker (different command) keeps build/deploy simple and guarantees code parity for domain logic in jobs.

## 3. Environments

| Env | Purpose | Data | Deploy trigger |
|-----|---------|------|----------------|
| dev | local docker-compose (postgres+postgis+pgvector, redis, mailpit) | seeded fixtures | — |
| staging | scaled-down mirror on AWS | anonymized production subset | merge to `main` |
| production | full topology | live | manual approval on release tag |

All AWS + Cloudflare resources defined in **Terraform** (`infra/terraform`, state in S3 + DynamoDB lock). No console-created resources — drift detection in CI weekly.

## 4. Networking & security

- VPC: public subnets (ALB only) + private app subnets + private data subnets; NAT for egress; VPC endpoints for S3/Secrets Manager.
- Security groups: ALB→api:3000 only; api/worker→ml:8000; api/worker→Redis:6379; DB access restricted to app CIDR + Supabase network rules.
- Container hardening: non-root user, read-only root FS, dropped capabilities, distroless/slim bases, Trivy scan gate.

## 5. Resilience & DR

- **Backups:** Supabase PITR (RPO ≤ 1 h) + nightly logical dump to S3 cross-region; Redis is reconstructible (no durable truths in Redis — invariant).
- **RTO 4 h runbook:** restore DB → redeploy tasks (stateless) → replay outbox/DLQ. Drilled quarterly (NFR-A2).
- **Graceful degradation:** ML down → circuit breaker serves last predictions flagged stale; OpenAI down → copilot offline banner; weather API down → staleness indicators; Redis down → API serves reads (cache-miss mode), writes queue locally with backpressure.
- Report/image storage: S3 versioning + lifecycle (IA at 90 d, Glacier at 1 y for audit archives).

## 6. Capacity plan (launch → year 1)

| Resource | Launch | Year-1 headroom trigger |
|----------|--------|------------------------|
| api tasks | 2 × 1 vCPU/2 GB | scale-out > 60% CPU sustained |
| worker | 1 × 2 vCPU/4 GB | queue depth > 1k for 10 min |
| ml | 1 × 2 vCPU/8 GB | batch window > 2 h (NFR-P3) |
| DB | 4 vCPU/16 GB, 100 GB | connections > 70% pool; storage 70% |
| Redis | cache.t4g.medium replicated | memory > 70% |

## 7. Cost guards

Budget alarms per service tag; OpenAI spend metered in-app (FR-AI-8) with CloudWatch export; weather API calls bounded by grid-cell dedup (FR-WX-1); S3 lifecycle policies; staging auto-sleeps nights/weekends (scheduled scale-to-zero for compute).

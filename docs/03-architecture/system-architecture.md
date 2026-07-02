# System Architecture

**Version:** 1.0.0 · Diagrams in Mermaid (render on GitHub).

> **⚠ Amended by [ADR-0001](../adr/0001-python-backend-no-docker.md):** the backend is now a single **Python/FastAPI modular monolith** (absorbing the ML service into the same runtime), with **no Docker dependency** and **no Redis** (PostgreSQL-backed jobs replace BullMQ; in-process caches replace Redis cache). Read Node/Express/Redis/ECS references below through that lens; the module boundaries, Clean Architecture layering, outbox pattern, API contract, and data design are unchanged.

---

## 1. Architectural Style & Key Decisions

### AD-1: Modular Monolith API + one ML microservice (not full microservices)

**Options considered:**

| Option | Pros | Cons |
|--------|------|------|
| Full microservices (per module) | Independent scaling/deploys | 20 modules → enormous operational overhead for one team; distributed transactions across farmer/farm/inventory; premature |
| Single monolith incl. ML | One deployable | Python ML ecosystem doesn't fit Node runtime; ML resource profile (CPU/memory spikes) starves API |
| **Modular monolith (Node) + ML microservice (Python)** ✅ | Clean module boundaries with in-process calls; single DB transaction scope for business ops; ML isolated where the language/runtime boundary is real | Requires discipline (enforced by lint boundaries) |

The module boundaries follow DDD bounded contexts, so extraction to services later is a mechanical move, not a rewrite. **CQRS is applied selectively**: writes go through the domain layer; heavy reads (dashboard, GIS viewport, reporting) use dedicated read models (SQL views + materialized views) — full event-sourced CQRS would add complexity with no proportional benefit at this scale.

### AD-2: Event-driven internals via outbox + BullMQ

Domain events (e.g., `DiseaseReportConfirmed`, `StockBelowCoverage`) are written to an **outbox table in the same transaction** as the state change, then relayed to BullMQ. This guarantees no lost events (vs. publish-after-commit races) without introducing Kafka-class infrastructure prematurely.

### AD-3: Supabase PostgreSQL as the single system of record

PostGIS (geospatial), pgvector (embeddings), and relational data live in one database. This enables joins between embeddings/geo/business data (e.g., "chunks about drought near affected farms"), one backup story, and one transaction scope. Read scaling later via read replicas; the reporting/Power BI schema reads from views to keep that decoupled.

### AD-4: LangChain orchestration with guarded-SQL semantic layer

The copilot never touches raw tables. A curated set of `semantic.*` views (documented, stable, PII-free) is the only SQL surface; generation is validated (SELECT-only, allow-listed relations, LIMIT enforced) and executed under a read-only role. This converts "text-to-SQL hallucination risk" into a bounded, auditable capability.

---

## 2. System Architecture Diagram (C4: Container level)

```mermaid
graph TB
    subgraph Clients
        WEB["React SPA<br/>(Vite · TS · Tailwind · shadcn)"]
        PBI["Power BI"]
    end

    subgraph Edge
        CF["Cloudflare<br/>WAF · CDN · DDoS"]
        NGINX["Nginx<br/>TLS · reverse proxy"]
    end

    subgraph "Application Tier (AWS ECS)"
        API["Node.js API<br/>Express · Modular Monolith<br/>REST + Socket.IO"]
        WORKERS["Background Workers<br/>BullMQ consumers<br/>(ingestion · scoring · notifications · reports)"]
        ML["ML Service<br/>Python · FastAPI<br/>XGBoost · sklearn · OR-Tools"]
    end

    subgraph "Data Tier"
        PG[("Supabase PostgreSQL<br/>PostGIS · pgvector<br/>+ semantic layer views")]
        REDIS[("Redis<br/>cache · sessions · BullMQ")]
        S3[("Object Storage<br/>images · documents · reports")]
    end

    subgraph "External Services"
        OPENAI["OpenAI API<br/>chat · embeddings"]
        WX["Weather Provider API"]
        COMMS["Email (SES) · SMS (Twilio)"]
    end

    WEB -->|HTTPS| CF --> NGINX --> API
    PBI -->|read-only reporting schema| PG
    API <-->|WebSocket| WEB
    API --> PG
    API --> REDIS
    API --> S3
    API -->|REST, internal network| ML
    API -->|LangChain| OPENAI
    WORKERS --> PG
    WORKERS --> REDIS
    WORKERS --> ML
    WORKERS --> WX
    WORKERS --> COMMS
    WORKERS --> OPENAI
    ML --> PG
```

**Notes:** Workers run the same codebase as the API in a separate process/task (different entrypoint) — one deploy artifact, independent scaling and failure isolation. The ML service is reachable only on the private network.

## 3. Component Diagram (API internal — Clean Architecture)

```mermaid
graph TB
    subgraph "Presentation Layer"
        ROUTES["HTTP Routes<br/>(per feature module)"]
        WS["Socket.IO Gateway"]
        MW["Middleware<br/>auth · rbac · validation(zod) · rate-limit · error"]
    end

    subgraph "Application Layer"
        UC["Use Cases / Application Services<br/>(commands + queries)"]
        EVH["Domain Event Handlers"]
        JOBS["Job Definitions (BullMQ)"]
    end

    subgraph "Domain Layer"
        ENT["Entities · Value Objects · Aggregates"]
        DS["Domain Services<br/>(risk rules, stock policy, outbreak detection)"]
        REPOI["Repository Interfaces (ports)"]
        DE["Domain Events"]
    end

    subgraph "Infrastructure Layer"
        REPO["Prisma Repositories (adapters)"]
        GEO["PostGIS Query Adapter (typed raw SQL)"]
        VEC["pgvector Adapter"]
        CACHE["Redis Cache Adapter"]
        QUEUE["BullMQ Producer/Consumer"]
        MLC["ML Service Client"]
        AIC["AI Orchestrator (LangChain)"]
        EXT["External Clients (weather, email, SMS, storage)"]
        OUTBOX["Transactional Outbox Relay"]
    end

    ROUTES --> MW --> UC
    WS --> UC
    UC --> ENT
    UC --> DS
    UC --> REPOI
    UC --> DE
    EVH --> UC
    JOBS --> UC
    REPOI -.implemented by.-> REPO
    DE -.persisted via.-> OUTBOX -.relayed to.-> QUEUE --> EVH
    UC -.ports to.-> MLC & AIC & CACHE & EXT
    REPO --> GEO
    REPO --> VEC
```

**Dependency rule (enforced by dependency-cruiser in CI):** `presentation → application → domain ← infrastructure`. The domain layer imports nothing from outer layers. Each of the 20 feature modules owns its slice of all four layers (feature-based folder structure — see folder-structure.md).

## 4. Sequence Diagrams

### 4.1 Authentication with refresh rotation

```mermaid
sequenceDiagram
    participant B as Browser
    participant A as API
    participant R as Redis
    participant D as PostgreSQL

    B->>A: POST /auth/login {email, password}
    A->>D: fetch user + Argon2id verify
    A->>D: insert refresh_token (family, hash)
    A-->>B: 200 {accessToken(15m)} + Set-Cookie refresh (httpOnly)
    Note over B: access token kept in memory only

    B->>A: GET /api/v1/farmers (expired token)
    A-->>B: 401 TOKEN_EXPIRED
    B->>A: POST /auth/refresh (cookie)
    A->>D: validate hash · check family not revoked
    alt reuse detected (token already rotated)
        A->>D: revoke entire family
        A-->>B: 401 → force re-login + security audit event
    else valid
        A->>D: rotate: revoke old, insert new
        A-->>B: 200 new access + new refresh cookie
    end
```

### 4.2 Disease report → outbreak alert (event-driven)

```mermaid
sequenceDiagram
    participant FO as Field Officer (SPA)
    participant A as API
    participant D as PostgreSQL
    participant Q as BullMQ
    participant W as Worker
    participant AG as Agronomist (SPA)

    FO->>A: POST /crops/disease-reports (+photos)
    A->>D: TX: insert report + outbox(DiseaseReportCreated)
    A-->>FO: 201
    D-->>Q: outbox relay → enqueue
    Q->>W: DiseaseReportCreated
    W->>D: spatial cluster query (10km/7d, same disease)
    alt cluster ≥ threshold
        W->>D: TX: escalate reports + create recommendation + outbox(OutbreakDetected)
        Q->>W: OutbreakDetected → notification pipeline
        W->>AG: Socket.IO alert + email
    end
    W->>D: recompute regional disease risk score
```

### 4.3 Copilot grounded data query

```mermaid
sequenceDiagram
    participant U as Executive (SPA)
    participant A as API (AI Orchestrator)
    participant O as OpenAI
    participant D as PostgreSQL (read-only role)

    U->>A: POST /copilot/conversations/:id/messages (stream)
    A->>A: load conversation memory + semantic-layer catalog
    A->>O: intent classification
    alt data query
        A->>O: generate SQL (catalog + few-shots in prompt)
        A->>A: validate: SELECT-only · allow-listed views · inject LIMIT
        A->>D: execute (statement_timeout 5s, ro role)
        alt SQL error
            A->>O: one repair attempt with error
        end
        A->>O: compose answer + chart spec from result rows
        A-->>U: stream tokens + citations + chart spec
    else ungroundable
        A-->>U: explicit refusal + what data would be needed
    end
    A->>D: persist turn + executed SQL (audit)
```

### 4.4 Nightly yield scoring

```mermaid
sequenceDiagram
    participant S as Scheduler (cron)
    participant W as Worker
    participant D as PostgreSQL
    participant M as ML Service

    S->>W: yield.batchScore (02:00)
    W->>D: select active crop cycles + assemble features<br/>(variety, soil, weather aggregates, history)
    loop batches of 500
        W->>M: POST /v1/predict/yield
        M-->>W: predictions + intervals + confidence + model_version
        W->>D: insert yield_predictions (immutable, feature snapshot ref)
    end
    W->>D: refresh materialized views (dashboard aggregates)
    W->>W: evaluate recommendation rules on deltas > 20%
```

## 5. Deployment Diagram

```mermaid
graph TB
    subgraph "Cloudflare"
        WAF["WAF · CDN · DNS"]
    end

    subgraph "AWS VPC"
        subgraph "Public subnets"
            ALB["ALB / Nginx"]
        end
        subgraph "Private subnets — ECS Fargate"
            API1["api ×2..N (autoscale)"]
            WRK1["worker ×1..N (scale on queue depth)"]
            ML1["ml-service ×1..N"]
        end
        subgraph "Private subnets — data"
            REDIS["ElastiCache Redis"]
        end
        S3["S3: images · documents · reports · ML artifacts"]
        SM["Secrets Manager"]
        CW["CloudWatch + OTel collector"]
    end

    subgraph "Supabase (managed)"
        PGP[("PostgreSQL primary<br/>PostGIS · pgvector · PITR")]
    end

    USERS["Users"] --> WAF --> ALB --> API1
    API1 & WRK1 & ML1 --> PGP
    API1 & WRK1 --> REDIS
    API1 & WRK1 & ML1 --> S3
    API1 & WRK1 & ML1 --> SM
    API1 & WRK1 & ML1 --> CW
```

Environments: **dev** (docker-compose, local Supabase or dev project) → **staging** (scaled-down mirror, anonymized data) → **production**. Web SPA is served as static assets from S3 + Cloudflare CDN; only `/api` and `/socket.io` hit the ALB. Socket.IO uses the Redis adapter so any API instance can deliver events (sticky sessions not required beyond the WS handshake).

## 6. Cross-Cutting Concerns

| Concern | Approach |
|---------|----------|
| Configuration | 12-factor env vars, validated at boot with Zod (`config` package); fail-fast on missing/invalid |
| Error handling | Central error taxonomy (`AppError` hierarchy: Validation, NotFound, Forbidden, Conflict, Domain, Infra); one Express error middleware maps to RFC 7807 problem+json |
| Idempotency | Mutating endpoints accept `Idempotency-Key`; workers use job IDs + upsert semantics |
| Caching | Redis: permission sets (60 s), weather responses (per grid-cell TTL), semantic-layer catalog, copilot embeddings of FAQs; explicit invalidation on writes |
| Realtime | Socket.IO namespaces per concern (`/alerts`, `/tracking`), JWT-authenticated handshake, room-per-user + room-per-role |
| Observability | OpenTelemetry SDK in API/workers/ML; trace context propagated over HTTP and job payloads |
| Migrations | Prisma Migrate; raw SQL migrations for PostGIS/pgvector/views/triggers checked into the same pipeline; roll-forward-only policy in prod |

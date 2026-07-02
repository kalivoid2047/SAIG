# Security Architecture

**Model:** defense in depth across edge, application, data, AI, and operational layers. Every module ships with the checklist in §9 completed.

---

## 1. Threat Model (STRIDE summary)

| Threat | Primary vectors here | Key mitigations |
|--------|---------------------|-----------------|
| Spoofing | Credential stuffing, token theft | Argon2id, lockout, short-lived JWT, refresh rotation + reuse detection, MFA-ready |
| Tampering | Payload manipulation, SQL injection, stock/audit falsification | Zod validation, Prisma parameterization, append-only ledgers, immutable audit |
| Repudiation | "I never approved that transfer" | Audit log (who/what/when/before/after) on all mutations of sensitive entities |
| Information disclosure | Farmer PII leaks, IDOR, LLM exfiltration | RBAC + org scoping on every query, PII permission tier, semantic layer PII exclusion, masked logs |
| Denial of service | Auth/AI endpoint abuse, expensive geo queries | Cloudflare WAF/DDoS, tiered rate limits, statement timeouts, pagination caps |
| Elevation of privilege | Role manipulation, mass assignment | Server-side permission checks, contract-whitelisted request bodies, admin actions dual-logged |

## 2. Identity & Access

### 2.1 Authentication
- Passwords: **Argon2id** (m=64 MB, t tuned ≥ 250 ms, unique salt). Breach-list check (zxcvbn + local top-100k list) at set time.
- **Access token:** JWT RS256 (asymmetric so ML service/workers can verify without the signing key), 15 min TTL, kept in SPA memory only (never localStorage).
- **Refresh token:** opaque 256-bit random, stored hashed (SHA-256) server-side, delivered as `httpOnly; Secure; SameSite=Strict; Path=/api/v1/auth` cookie, 7-day TTL, **rotated on every use**; reuse of a rotated token revokes the whole token family and raises a security event.
- Session revocation: user deactivation / password reset / admin action revokes families; access tokens die naturally ≤ 15 min (blocklist for immediate-kill cases, Redis, TTL = remaining token life).

### 2.2 Authorization (RBAC)
- Permission = `resource:action` (e.g., `inventory:transfer`, `farmers:read_pii`). Roles bundle permissions; users hold roles per organization.
- Enforced at **three layers**: route middleware (declared per endpoint), application-layer assertion (defense against future route mistakes), and **org scoping in every repository query** (tenant isolation is a query concern, not a trust concern).
- UI hides unauthorized surfaces, but the server is the only authority.

## 3. OWASP Top 10 mapping (2021)

| # | Risk | Controls |
|---|------|----------|
| A01 Broken Access Control | RBAC middleware + repo-level org scoping; IDOR prevented by scoped lookups (`WHERE id = ? AND organization_id = ?`); deny-by-default routing |
| A02 Cryptographic Failures | TLS 1.2+ (HSTS preload); AES-256 at rest (DB, S3, backups); Argon2id; no custom crypto |
| A03 Injection | Prisma parameterized queries; typed raw SQL via parameter binding only; Zod validation on every input incl. query/params/headers; guarded-SQL allow-list for copilot; no shell-outs |
| A04 Insecure Design | This document + threat model per module; abuse cases in QA suites |
| A05 Security Misconfiguration | Helmet headers (§5); env validated at boot; containers non-root, read-only FS; IaC-reviewed infra; no default creds |
| A06 Vulnerable Components | Dependabot + `pnpm audit`/`pip-audit` gates in CI; base image scanning (Trivy); lockfiles committed |
| A07 Auth Failures | §2.1 controls; generic auth errors (no enumeration); lockout + audit |
| A08 Integrity Failures | Signed container images; CI provenance; webhook/report links signed + expiring; no `eval`/dynamic require |
| A09 Logging Failures | Structured audit + security events; alerting on anomalies (lockout bursts, refresh-reuse); logs PII-scrubbed |
| A10 SSRF | Outbound HTTP only via allow-listed gateway clients; document/URL ingestion validates schemes + blocks private IP ranges |

## 4. Input Validation & API hygiene

- Every route validates `body`, `query`, `params` against `@saig/contracts` Zod schemas — **unknown keys stripped** (mass-assignment defense), sizes bounded, enums closed.
- File uploads: MIME sniffing (magic bytes, not extension), size caps, ClamAV scan, images re-encoded (EXIF stripped except consented GPS), stored under random keys, served via signed URLs from a cookie-less domain.
- Pagination hard cap (100), geo bbox area cap, report date-range caps — resource-exhaustion guards.

## 5. Secure headers & browser protections

Helmet configuration: `Strict-Transport-Security` (2y, preload), `Content-Security-Policy` (default-src 'self'; connect-src API + tiles; frame-ancestors 'none'), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` minimal (geolocation only where field capture needs it).

**CSRF:** the refresh cookie is the only ambient credential; it is `SameSite=Strict` and scoped to the auth path; all state-changing APIs require the Bearer token (not a cookie) → CSRF surface is structurally minimal. Additionally, `Origin` header verification on auth endpoints.

**XSS:** React auto-escaping; no `dangerouslySetInnerHTML` (lint-banned) except the markdown renderer, which sanitizes via a strict allow-list (rehype-sanitize); CSP as backstop; copilot output treated as untrusted content (rendered through the same sanitizer — LLM output is an injection vector).

## 6. Rate limiting & abuse control

| Surface | Limit (per user unless noted) | Backing |
|---------|------------------------------|---------|
| `/auth/login` | 5/15 min per IP + per account | Redis sliding window |
| `/auth/refresh` | 10/min | Redis |
| General API | 300/min | Redis |
| Copilot messages | 20/min + daily token budget | Redis + metering |
| Uploads | 20/hour | Redis |
| Report generation | 10/hour | Redis |

429 responses include `Retry-After`. Cloudflare provides the coarse outer layer (bot fight, geo rules).

## 7. Data protection

- **Classification:** P0 farmer PII (national ID, phone, precise home location) · P1 business-sensitive (forecasts, financials) · P2 operational.
- P0: dedicated permission tier (`*_pii`), masked by default in UI and logs, column-level grants keep it out of the reporting and semantic schemas, access audit-logged (FR-FRM-5). Right-to-erasure via anonymization job that preserves statistical aggregates (NFR-C1).
- **Secrets:** AWS Secrets Manager; injected at runtime; never in images, code, or CI logs; rotation runbook per credential; separate DB roles: `app_rw`, `copilot_ro` (semantic only), `reporting_ro`, `migrations`.
- **Audit log:** append-only table; `app_rw` role has INSERT-only grant (no UPDATE/DELETE); includes actor, action, entity, before/after JSONB, IP, request ID; retained ≥ 2 years, archived to S3 Glacier.

## 8. AI-specific security

- **Prompt injection:** retrieved document chunks and user text are delimited and declared untrusted in the system prompt; instructions in retrieved content are ignored by policy; output verifier blocks answers containing tool-instruction artifacts; documents from uploads can't grant themselves permissions (RBAC filter is in SQL, pre-context).
- **Exfiltration:** semantic layer contains no PII; copilot role physically cannot read PII columns; conversations are org-scoped.
- **Model output as attack surface:** rendered through sanitizer (§5); chart specs validated against a Zod schema before render (no arbitrary component props).
- **Third-party boundary:** only aggregated/anonymized business data reaches OpenAI; DPA + zero-retention API tier; feature flag to disable external AI per org.

## 9. Per-module security review checklist (gate for every module PR)

1. All routes declare permissions; org scoping verified in repository tests.
2. Contracts validate every input; unknown-key stripping confirmed.
3. New tables: soft-delete + audit coverage decided and implemented; PII classified.
4. New external calls: gateway client with timeout, retry budget, allow-listed host.
5. New background jobs: idempotent, DLQ-covered, no secrets in payloads.
6. Threat-model delta reviewed (what new abuse does this module enable?).
7. Security tests added (authz matrix test per route: each role × endpoint → expected 200/403).

## 10. Incident response (summary)

Detection (alert classes: auth anomalies, WAF spikes, refresh-reuse, audit gaps, data-egress anomalies) → triage severity matrix → containment playbooks (revoke families, rotate secrets, block at edge) → post-incident review with ADR-style writeup. Full runbook lives in `docs/runbooks/` (authored during Phase 0).

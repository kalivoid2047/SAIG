# ADR-0003: In-process ML plane with scikit-learn baseline

**Status:** Accepted · **Date:** 2026-07-04 · **Context:** Phase 3 (Predictive Core)

## Context

The system architecture (AD-1) originally placed a **separate Python FastAPI ML microservice** alongside a Node backend. ADR-0001 removed the Node tier and made the backend a single Python/FastAPI modular monolith, noting the ML plane would "run in-process or as a separately started uvicorn worker later." Phase 3 must now deliver the predictive core: yield prediction and demand forecasting, with model lineage and confidence.

Two open questions from earlier phases bear on this:
- No separate runtime boundary remains (the API is already Python), so an internal HTTP hop between "API" and "ML service" would add operational cost with no language/isolation benefit at current scale.
- Real historical training data (soil + weather at harvest time) is not yet available; models must be trainable and testable from the data we do capture.

## Decision

1. **The ML plane runs in-process** as two cooperating packages inside `apps/api`:
   - `saig/ml/` — the pure, framework-free data-science core: feature engineering, model wrappers, and a model registry. No FastAPI, no DB session — it takes DataFrames/dicts and returns predictions. This keeps it unit-testable and *extractable* to a separate service later without rewriting.
   - `saig/modules/predictions/` — the prediction bounded context: lineage tables, DB orchestration (assemble features → call `saig/ml` → persist immutable predictions), and the REST surface.
2. **scikit-learn is the baseline, not XGBoost.** `GradientBoostingRegressor` with quantile loss gives yield point estimates *and* 80% prediction intervals with zero native-build risk on Windows/CI. XGBoost remains a documented drop-in upgrade behind the same `saig/ml` model interface; adopting it is a dependency swap, not an architecture change.
3. **Model artifacts** are persisted with `joblib` under a local `artifacts/` directory in dev (git-ignored), and to object storage in production — abstracted behind the registry so callers never touch paths. A `model_versions` table records version, metrics, artifact key, and promotion status; **only a `promoted` version serves** (BR-3, FR-YLD-4).
4. **Every prediction stores its lineage**: the model version and a JSONB **feature snapshot** of exactly the inputs used — satisfying reproducibility (BR-3) and enabling "why did the number change" audits. Predictions are immutable; re-scoring appends a new run.
5. **Training is an offline, explicit step** (`saig/scripts/train_models.py`) that reads the DB, trains, evaluates, registers, and promotes — mirroring the MLOps loop in ai-architecture.md. It is not triggered by request traffic.

## Consequences

- **Positive:** one runtime to run and deploy (Docker-free, ADR-0001 intact); in-process feature assembly with no serialization hop; models/features/lineage all in one transaction scope; deterministic, network-free tests (train a tiny model in a fixture, score, assert).
- **Trade-offs accepted:** heavy scientific deps (numpy/pandas/sklearn ~200 MB) now load in the API process — acceptable at current scale; if model latency or memory becomes an issue, the `saig/ml` seam allows moving scoring to a dedicated worker/service. Batch scoring runs synchronously via a script/endpoint until the PostgreSQL-backed job runner (ADR-0001) lands, at which point it becomes a scheduled job (UC-04).
- **Scope:** this ADR was written for yield + demand; the same in-process, pure-core philosophy was extended to the rest of Phase 3 — risk intelligence (six-domain scoring), OR-Tools capacitated VRP route optimization (`saig/ml/routing.py`, with a pure nearest-neighbour + 2-opt fallback behind the same `optimize` interface), and model evaluation (rolling-origin demand backtest + yield predicted-vs-actual). All are now shipped.
- **Docs:** ai-architecture.md §2 (Prediction Engine) is realized by `saig/ml` + `saig/modules/predictions`; the "XGBoost" references there should be read as "gradient-boosted trees (sklearn baseline, XGBoost-upgradable)."

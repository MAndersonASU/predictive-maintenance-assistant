# Application Foundation

## Purpose

This layer exposes the already-frozen predictive-maintenance model and the already-governed technical-knowledge stack through a bounded local API. It adds local persistence, structured operational events, health/readiness checks, request validation, safe error handling, and integration tests. It does **not** refit the Isolation Forest, change its 48-feature set or threshold, rerun held-out evaluation, rebuild the 354-chunk corpus, rebuild or retune the hybrid retrieval index, or weaken citation/equipment-evidence boundaries.

## Local API contract

The FastAPI application is created by `predictive_maintenance.application.api:create_app` and is configured by `config/application.json`.

- `GET /health/live` — process liveness only.
- `GET /health/ready` — verifies required frozen local artifacts and persistence availability.
- `GET /api/v1/prediction/schema` — returns the exact frozen prediction feature names and threshold metadata.
- `POST /api/v1/predict` — accepts an object named `features` whose keys must match the frozen feature set exactly. The returned Isolation Forest value is an unusualness score, not a failure probability. `alarm=true` means only that the score is strictly greater than the frozen threshold.
- `POST /api/v1/retrieve` — runs the existing governed hybrid retriever with bounded `top_k` and preserves retrieval provenance.
- `POST /api/v1/answer` — runs the existing deterministic reranking and citation-grounded answer path, including insufficient-evidence refusal for exact-equipment requests when exact equipment evidence is absent.
- `POST /api/v1/evaluations` — records a bounded local human-review outcome (`pass`, `fail`, or `needs_review`) for a prediction, retrieval, or grounded-answer interaction. These records are demonstration review evidence, not model/RAG benchmark results.
- `GET /api/v1/evaluations` — returns bounded local review records.
- `GET /api/v1/history` — returns a bounded local demonstration history.
- `GET /api/v1/metrics` — returns bounded in-process counters plus local persistence counts.

FastAPI supplies OpenAPI and the local interactive documentation surface. The release is intentionally bound to loopback (`127.0.0.1`) and is not a public deployment.

## Persistence and privacy boundary

SQLite is used because the current requirement is bounded local demonstration persistence rather than a production database service. The database is created under `data/interim/application/`, which is already excluded from Git. Every transaction-scoped SQLite connection is explicitly closed after commit or rollback so Windows does not retain database-file handles between requests or tests.

Prediction records do not persist raw feature values by default. Request headers are never persisted. Retrieval history stores the query and a result-count summary rather than duplicating retrieved evidence text. Grounded-answer history stores status, reason, intent, and citation count rather than the full answer payload. Retention is bounded independently for interaction records, local review evaluations, and operational events.

## Operational evidence

Every HTTP request receives an `X-Request-ID`. Structured JSON logs emit request completion metadata without request bodies or headers. SQLite application events record bounded request status and failure information. In-memory counters expose request, error, alarm/non-alarm, retrieval, and grounded-answer status counts for demonstration monitoring.

Dependency failures return sanitized `503` responses. Input/schema failures return controlled `422` responses. Internal governed artifact paths and raw exception details are not returned to API clients.

## Secret handling and security scope

Committed configuration may contain environment-variable **names** but not secret values. Secret-like config keys containing non-empty values are rejected. Public-network exposure is prohibited by the current config validator, and the runtime refuses a non-loopback host when the loopback control is enabled.

Authentication is intentionally disabled because this milestone is a bounded local demonstration, not a public or multi-user service. Public deployment would require a separately designed authentication, authorization, TLS, secret-management, rate-limiting, and network policy boundary.

## Run locally

From the repository root with the virtual environment active and `PYTHONPATH=src`:

```powershell
python -m predictive_maintenance.application.api
```

The configured local server is `127.0.0.1:8000`. Interactive API documentation is available at `/docs` after startup.

## Verification expectations

The application-specific tests cover configuration/path/secret controls, bounded SQLite retention, explicit SQLite connection closure, frozen prediction artifact identity, exact feature validation, unusualness-score semantics, retrieval/grounding delegation, readiness checks, API validation, sanitized failures, redacted persistence, request IDs, local review evaluations, history, metrics, and OpenAPI path exposure. Starlette TestClient verification uses the supported `httpx2` client dependency. The complete repository regression suite must also pass before the implementation is committed.

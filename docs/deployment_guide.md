# Bounded Local Deployment Guide

## Deployment contract

The supported release target is a local demonstration on loopback. Governed model and retrieval artifacts remain outside Git and are consumed read-only. Startup does not fit a model, rebuild the corpus or index, retune grounding, or run held-out evaluation.

## Required local artifacts

Place the verified files at these project-relative paths:

- `outputs/metropt3_selected_isolation_forest.joblib`
- `outputs/metropt3_robust_distance_parameters.json`
- `outputs/metropt3_isolation_forest_validation_report.json`
- `data/interim/knowledge/chunks.jsonl`
- `data/interim/knowledge/retrieval/hybrid_index.joblib`

Run the non-destructive release audit before startup:

```powershell
$env:PYTHONPATH = "src"
python -m predictive_maintenance.release_audit --repository-root .
```

The command writes the ignored report `outputs/release_candidate_audit.json`. A passing report confirms the committed release-document inventory, frozen configuration, artifact SHA-256 values, 354-chunk count, loopback/privacy controls, and self-contained interface boundary. It does not rerun either held-out evaluator.

## Native Windows start

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH = "src"
python -m pip check
python -m pytest -q
python -m predictive_maintenance.application.api
```

Open `http://127.0.0.1:8000/`. OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Docker start

```powershell
docker compose config --quiet
docker compose build --no-cache
docker compose up -d
docker compose ps
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/live"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready"
```

Readiness must report `ready` before prediction, retrieval, or answer requests are treated as available. Stop normally with:

```powershell
docker compose down
```

Do not use `docker compose down -v` unless intentionally deleting the bounded local application-history volume.

## Verification expectations

- The complete repository suite passes with warnings reviewed.
- `python -m pip check` reports no broken requirements.
- The release audit passes without changing governed artifacts.
- The documented module startup produces no import warning.
- Liveness and readiness pass.
- Prediction uses exactly 48 frozen features and the frozen threshold.
- Knowledge responses preserve citations, provenance, and exact-equipment refusal.
- The browser interface loads only committed local assets.
- The service is published only on host loopback.
- Temporary native or container services are stopped after review.

## Public deployment boundary

This guide does not authorize public exposure. A public service would require separately implemented authentication, authorization, TLS, rate limiting, secret management, durable production storage, network policy, image vulnerability/signing controls, backup and recovery, alerting, scaling, and named operational ownership.

See `docs/container_execution.md` for the complete container contract and `docs/application_foundation.md` for API, persistence, and security controls.

# Intelligent Predictive Maintenance and Technical Knowledge Assistant

[![CI](https://github.com/MAndersonASU/predictive-maintenance-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/MAndersonASU/predictive-maintenance-assistant/actions/workflows/ci.yml)

A professional engineering portfolio project that combines governed industrial time-series analysis, anomaly detection, and citation-grounded technical knowledge retrieval for predictive-maintenance applications.

## Current Verified Capability

The repository is implemented as a bounded local release candidate through six connected foundations:

1. **Governed data engineering** — reproducible MetroPT-3 acquisition, checksums, schema and data-quality validation, Parquet conversion, DuckDB access, and gap-aware exploratory analysis.
2. **Governed machine learning** — auditable failure-event provenance, chronological target materialization, causal feature engineering, a transparent robust-distance benchmark, a bounded Isolation Forest comparison, and one-time held-out evaluation with frozen parameters.
3. **Governed technical knowledge** — a three-source corpus with explicit source roles, deterministic extraction and chunking, provenance preservation, and source-completeness controls.
4. **Citation-grounded answers** — TF-IDF keyword retrieval, deterministic 128-dimensional LSA embeddings, bounded hybrid retrieval, deterministic reranking, bounded evidence assembly, stable citations, and explicit insufficient-evidence refusal.
5. **Application and operations** — loopback-only prediction, retrieval, and answer APIs; strict validation; bounded SQLite persistence; structured operational events; readiness; counters; and sanitized failures.
6. **Reproducible professional demonstration** — a self-contained browser interface over the governed API path plus a pinned, hardened Docker runtime with read-only governed artifact mounts.

The pre-release integration checkpoint contained **362 passing tests**. Use the exact release-candidate commit and its GitHub Actions run as the authority for the current count.

## Machine-Learning Release

The selected advanced candidate is `iforest_ne200_ms4096_mf1p0` with frozen threshold `0.601902290159477` and a frozen 48-feature set.

| Governed held-out measure | Isolation Forest | Robust-distance baseline |
|---|---:|---:|
| Documented-event coverage | 1.000 | 1.000 |
| Mean first-alarm latency, covered events (s) | 218.000 | 15804.000 |
| Alarms per 24 observed hours | 69.863 | 94.192 |

These are operational measures, not conventional classification metrics. Unverified operational rows are not treated as verified healthy negatives, alarm burden is not a false-positive rate, and unusualness is not failure probability.

## Technical-Knowledge System

The governed corpus contains **3 sources and 354 deterministic chunks**:

- UCI MetroPT-3 dataset documentation — exact dataset evidence.
- Scientific Data MetroPT publication — related dataset/project evidence with an explicit collection-scope boundary.
- U.S. Department of Energy compressed-air sourcebook — authoritative general guidance, not an exact MetroPT equipment manual.

Retrieval uses a 16,000-feature TF-IDF representation, deterministic 128-dimensional LSA embeddings, and bounded hybrid fusion. The grounding layer reranks results deterministically, preserves source identity and locators, creates stable `[S#]` citations, and refuses manufacturer- or model-specific equipment instructions when exact-equipment evidence is unavailable.

The frozen twelve-case RAG evaluation reports source Hit@1/3/5 of 0.625, mean reciprocal rank of 0.645833, 40/40 traceable citations, full source-scope alignment, full cited-claim support, and three preserved UCI-specific retrieval misses. These bounded results do not establish broad production quality or exhaustive factual coverage.

## Integrated System Architecture

```text
Governed MetroPT-3 Data
    -> checksums / schema / data-quality validation
    -> Parquet / DuckDB
    -> gap-aware targets and causal features
    -> transparent robust-distance benchmark
    -> frozen Isolation Forest
    -> held-out operational evaluation

Governed Technical Sources
    -> source governance / completeness checks
    -> deterministic extraction / normalization / chunking
    -> TF-IDF keyword retrieval + 128-dim LSA retrieval
    -> bounded hybrid fusion
    -> deterministic reranking
    -> bounded evidence assembly + stable citations
    -> citation-grounded answer or explicit insufficient-evidence refusal

Local Professional Interface
    -> frozen prediction schema and scoring
    -> retrieval + grounded answer + evidence inspection
    -> readiness, counters, and bounded local review evidence
    -> same loopback-only FastAPI contracts
```

See [`docs/system_architecture.md`](docs/system_architecture.md) for the current integrated architecture and [`docs/ml_architecture.md`](docs/ml_architecture.md) for the machine-learning subsystem.

## Quick Start

The repository uses a `src/` layout. The commands below create an isolated environment, install the pinned development/test dependency set, and run only safe regression checks.

### Windows PowerShell

```powershell
git clone https://github.com/MAndersonASU/predictive-maintenance-assistant.git
cd predictive-maintenance-assistant

py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

$env:PYTHONPATH = "src"
python -m pytest -q
python -m pip check
```

`requirements-dev.txt` pins the complete development/test dependency set used by CI on CPython 3.14 so fresh-clone verification does not silently drift with transitive dependency releases.

The governed held-out model evaluators are **not** part of routine verification and must not be rerun. See [`docs/ml_reproducibility.md`](docs/ml_reproducibility.md) for the frozen-release boundary.

### Run the bounded local interface

The configured governed artifacts must already exist at their documented ignored paths. With the virtual environment active:

```powershell
$env:PYTHONPATH = "src"
python -m predictive_maintenance.application.api
```

Open `http://127.0.0.1:8000/` for the professional demonstration or `http://127.0.0.1:8000/docs` for OpenAPI documentation. The interface remains local-only and does not claim public deployment readiness.

### Reproducible Docker start

After confirming the same governed artifacts exist, use the hardened local container path:

```powershell
docker compose config --quiet
docker compose build --no-cache
docker compose up -d
```

See [`docs/container_execution.md`](docs/container_execution.md) for artifact mounts, clean-start checks, and teardown commands.

## Continuous Integration

GitHub Actions runs Python compilation, the complete regression suite, and dependency consistency checks on pushes to `main` and on pull requests targeting `main`.

The workflow uses Node 24-compatible official action majors and the same pinned development/test dependencies documented in `requirements-dev.txt`.

The CI workflow intentionally does **not** execute data acquisition, model fitting, held-out scoring, corpus downloads, or other governed production workflows.

## Reproducibility

Generated datasets, reports, retrieval indexes, model artifacts, and downloaded technical sources remain outside Git under governed ignore rules. Runtime dependencies are declared in `requirements.txt`; the development/test verification environment is fully pinned in `requirements-dev.txt`.

Run the non-destructive frozen-artifact and release-document audit after restoring the governed local artifacts:

```powershell
$env:PYTHONPATH = "src"
python -m predictive_maintenance.release_audit --repository-root .
```

The ignored JSON report records document, configuration, artifact-identity, chunk-count, security-boundary, and self-contained-interface checks. The audit never fits, rebuilds, retunes, or runs held-out evaluation.

## Key Documentation

- [`ENGINEERING_LOG.md`](ENGINEERING_LOG.md) — verified engineering history and current workstream.
- [`docs/model_card.md`](docs/model_card.md) — frozen Isolation Forest model card.
- [`docs/data_card.md`](docs/data_card.md) — governed MetroPT-3 identity, transformations, uses, and limitations.
- [`docs/evaluation_summary.md`](docs/evaluation_summary.md) — machine-learning, retrieval, grounded-answer, and integration evidence.
- [`docs/data_feature_governance.md`](docs/data_feature_governance.md) — data, target, feature, and evaluation controls.
- [`docs/system_architecture.md`](docs/system_architecture.md) — integrated current architecture.
- [`docs/knowledge_corpus_method.md`](docs/knowledge_corpus_method.md) — governed technical corpus.
- [`docs/knowledge_retrieval_method.md`](docs/knowledge_retrieval_method.md) — bounded hybrid retrieval.
- [`docs/knowledge_grounding_method.md`](docs/knowledge_grounding_method.md) — reranking, citations, and refusal behavior.
- [`docs/application_foundation.md`](docs/application_foundation.md) — loopback API, persistence, operations, and security controls.
- [`docs/professional_demo.md`](docs/professional_demo.md) — demonstration workspaces, evidence presentation, and interface boundaries.
- [`docs/deployment_guide.md`](docs/deployment_guide.md) — native and Docker release startup and verification.
- [`docs/container_execution.md`](docs/container_execution.md) — pinned, hardened container contract.
- [`docs/portfolio_interview_guide.md`](docs/portfolio_interview_guide.md) — verified résumé, LinkedIn, and interview language.
- [`docs/release_candidate_checklist.md`](docs/release_candidate_checklist.md) — exact-commit release evidence gate.

## Engineering Principles

- Reproducible data, model, retrieval, and answer evidence.
- Chronological and gap-aware leakage controls.
- Transparent baselines before advanced models.
- Held-out evidence reserved for final reporting.
- No unsupported performance, reliability, or business-impact claims.
- Traceable technical sources and provenance-preserving citations.
- Exact-equipment claims require exact-equipment evidence.
- Secrets, generated outputs, large data, local databases, and model artifacts remain outside Git.

## Release-Candidate Boundary

The project is functionally integrated for bounded local demonstration. It is not a public production service, safety system, or proof of business impact. Release acceptance requires the clean-state checks, governed artifact identities, exact-commit CI evidence, and final synchronization recorded in the release-candidate checklist.

# Intelligent Predictive Maintenance and Technical Knowledge Assistant

A professional engineering portfolio project that combines governed industrial time-series analysis, anomaly detection, and citation-grounded technical knowledge retrieval for predictive-maintenance applications.

## Current Verified Capability

The repository is implemented and verified through four connected foundations:

1. **Governed data engineering** — reproducible MetroPT-3 acquisition, checksums, schema and data-quality validation, Parquet conversion, DuckDB access, and gap-aware exploratory analysis.
2. **Governed machine learning** — auditable failure-event provenance, chronological target materialization, causal feature engineering, a transparent robust-distance benchmark, a bounded Isolation Forest comparison, and one-time held-out evaluation with frozen parameters.
3. **Governed technical knowledge** — a three-source corpus with explicit source roles, deterministic extraction and chunking, provenance preservation, and source-completeness controls.
4. **Citation-grounded answers** — TF-IDF keyword retrieval, deterministic 128-dimensional LSA embeddings, bounded hybrid retrieval, deterministic reranking, bounded evidence assembly, stable citations, and explicit insufficient-evidence refusal.

The complete repository suite currently contains **276 passing tests**.

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

The current grounding smoke validation is implementation evidence only. Formal retrieval quality, citation correctness, faithfulness, answer usefulness, failure cases, and limitations are evaluated separately.

## System Architecture

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
```

See [`docs/system_architecture.md`](docs/system_architecture.md) for the current integrated architecture and [`docs/ml_architecture.md`](docs/ml_architecture.md) for the machine-learning subsystem.

## Reproducibility

From the repository root with the project virtual environment active:

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m pip check
```

Generated datasets, reports, retrieval indexes, model artifacts, and downloaded technical sources remain outside Git under governed ignore rules.

## Key Documentation

- [`ENGINEERING_LOG.md`](ENGINEERING_LOG.md) — verified engineering history and current workstream.
- [`docs/model_card.md`](docs/model_card.md) — frozen Isolation Forest model card.
- [`docs/ml_evaluation_report.md`](docs/ml_evaluation_report.md) — held-out machine-learning comparison.
- [`docs/data_feature_governance.md`](docs/data_feature_governance.md) — data, target, feature, and evaluation controls.
- [`docs/system_architecture.md`](docs/system_architecture.md) — integrated current architecture.
- [`docs/knowledge_corpus_method.md`](docs/knowledge_corpus_method.md) — governed technical corpus.
- [`docs/knowledge_retrieval_method.md`](docs/knowledge_retrieval_method.md) — bounded hybrid retrieval.
- [`docs/knowledge_grounding_method.md`](docs/knowledge_grounding_method.md) — reranking, citations, and refusal behavior.

## Engineering Principles

- Reproducible data, model, retrieval, and answer evidence.
- Chronological and gap-aware leakage controls.
- Transparent baselines before advanced models.
- Held-out evidence reserved for final reporting.
- No unsupported performance, reliability, or business-impact claims.
- Traceable technical sources and provenance-preserving citations.
- Exact-equipment claims require exact-equipment evidence.
- Secrets, generated outputs, large data, local databases, and model artifacts remain outside Git.

## Current Engineering Focus

The next governed engineering milestone is **retrieval and grounded-answer evaluation**. It must evaluate retrieval quality, citation correctness, faithfulness, answer usefulness, failure cases, and limitations separately before application/API integration is treated as release-ready.

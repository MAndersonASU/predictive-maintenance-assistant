# Intelligent Predictive Maintenance and Technical Knowledge Assistant

A professional AI engineering portfolio project that combines governed industrial time-series analysis, anomaly detection, and a planned citation-grounded technical-knowledge assistant.

## Current Verified Capability

The machine-learning foundation is complete through held-out evaluation. The repository includes reproducible MetroPT-3 acquisition and integrity checks, schema/data-quality validation, Parquet and DuckDB access, gap-aware exploratory analysis, governed event provenance and target materialization, causal feature engineering, a transparent robust-distance benchmark, and a bounded Isolation Forest comparison.

The selected advanced candidate is `iforest_ne200_ms4096_mf1p0` with frozen threshold `0.601902290159477`. It was selected using validation evidence only and evaluated once on the locked test partition after explicit authorization. Test evidence did not change the model, feature set, or threshold.

## Machine-Learning Evaluation

| Measure | Isolation Forest | Robust-distance baseline |
|---|---:|---:|
| Documented-event coverage | 1.000 | 1.000 |
| Mean first-alarm latency, covered events (s) | 218.000 | 15804.000 |
| Alarms per 24 observed hours | 69.863 | 94.192 |

These are governed operational measures. Alarm burden is not a false-positive rate, unusualness is not failure probability, and unverified operational rows are not treated as verified healthy negatives.

## Architecture

```text
Governed Sources
    -> validation and checksums
    -> Parquet / DuckDB
    -> governed targets
    -> causal features
    -> transparent baseline + frozen Isolation Forest
    -> held-out evaluation
    -> technical-knowledge retrieval (next)
    -> APIs / persistence / monitoring
    -> Docker / demonstration interface
```

## Reproducibility

With the virtual environment active from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

The one-time held-out advanced-model evaluation is governed by `config/metropt3_isolation_forest_test_evaluation.json` and refuses overwrite after completion.

## Project Principles

- Reproducible data and model evidence
- Chronological and gap-aware leakage controls
- Transparent baselines before advanced models
- Test data reserved for final reporting
- No unsupported performance or business-impact claims
- Traceable technical sources and citations
- Secure exclusion of secrets, raw/processed large data, generated outputs, and model artifacts from Git

## Next Release Milestone

Build the governed technical-document corpus and deterministic extraction/chunking pipeline. Exact equipment documentation will only be labeled as such when manufacturer and model identity are independently verified.

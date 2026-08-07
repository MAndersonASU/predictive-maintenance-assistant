"""Generate the machine-learning release documentation from frozen evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT = PROJECT_ROOT / "outputs" / "metropt3_isolation_forest_test_report.json"


class MLReleaseDocumentationError(ValueError):
    pass


def _read_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MLReleaseDocumentationError(f"Final test report does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("status") != "frozen_after_one_time_test_evaluation":
        raise MLReleaseDocumentationError("Final test evidence is not frozen.")
    if payload.get("governance", {}).get("one_time_advanced_model_test_evaluation_complete") is not True:
        raise MLReleaseDocumentationError("One-time advanced-model test evaluation is not complete.")
    return payload


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "not available"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def build_documents(report: dict[str, Any]) -> dict[str, str]:
    model = report["frozen_model"]
    test = report["advanced_model_test"]
    comparison = report["baseline_comparison"]
    adv = comparison["isolation_forest"]
    base = comparison["robust_distance_baseline"]

    model_card = f"""# Model Card — MetroPT-3 Isolation Forest

## Intended use

This model is a bounded anomaly-detection component for the Intelligent Predictive Maintenance and Technical Knowledge Assistant. It scores governed MetroPT-3 compressor observations for unusualness. It does not estimate failure probability and does not create a verified healthy class.

## Frozen model

- Candidate: `{model['candidate_id']}`
- Family: `sklearn.ensemble.IsolationForest`
- Retained features: {model['retained_feature_count']}
- Frozen alarm threshold: `{model['threshold']}`
- Model artifact SHA-256: `{model['model_sha256']}`
- Test-time refit: no
- Test-time threshold revision: no
- Test-driven candidate reselection: no

## Evaluation boundary

Model fitting and threshold derivation were training-only. Candidate selection was validation-only. The locked test partition was accessed once after explicit authorization and only after the candidate and threshold were frozen.

## Held-out evidence

- Eligible test rows scored: {test['scored_rows']}
- Documented-event coverage: {_fmt(test['documented_event_coverage_fraction'])}
- Mean first-alarm latency for covered events: {_fmt(test['mean_first_alarm_latency_seconds_for_covered_events'])} seconds
- Alarms per 24 observed hours: {_fmt(test['alarms_per_24_observed_hours'])}

## Limitations

- Unverified operational rows are not verified healthy negatives.
- Alarm burden is not a false-positive rate.
- Isolation Forest unusualness is not a failure probability.
- Documented-event evidence is limited to governed events present in the held-out partition.
- Held-out results cannot be used to retune this frozen release.
"""

    evaluation_report = f"""# Machine-Learning Evaluation Report

## Evaluation design

The machine-learning workstream uses chronological, segment-safe governance and a frozen 48-feature set. A transparent maximum-absolute-robust-z-score detector is retained as the finalized benchmark. The advanced model family was restricted in advance to eight Isolation Forest candidates. The selected candidate was frozen after validation and then evaluated once on the locked test partition.

## Held-out comparison

| Measure | Isolation Forest | Robust-distance baseline |
|---|---:|---:|
| Documented-event coverage | {_fmt(adv['documented_event_coverage_fraction'])} | {_fmt(base['documented_event_coverage_fraction'])} |
| Mean first-alarm latency, covered events (s) | {_fmt(adv['mean_first_alarm_latency_seconds_for_covered_events'])} | {_fmt(base['mean_first_alarm_latency_seconds_for_covered_events'])} |
| Alarms per 24 observed hours | {_fmt(adv['alarms_per_24_observed_hours'])} | {_fmt(base['alarms_per_24_observed_hours'])} |

## Interpretation

This table is a transparent held-out comparison, not a test-driven model-selection step. No feature, threshold, model parameter, or candidate was changed after test access.

## Supported claims

The repository may report the governed operational measures above and the exact evaluation protocol. It must not report false-positive rate, accuracy, precision, recall, calibrated failure probability, or verified healthy-class performance because the project does not have a verified negative class supporting those claims.

## Frozen release decision

The advanced candidate remains `{model['candidate_id']}` because it was selected before test access. The robust-distance detector remains the transparent benchmark. Test evidence is final reporting evidence only.
"""

    governance = """# Data and Feature Governance Summary

## Data identity

The machine-learning workstream uses the governed MetroPT-3 Air Production Unit compressor dataset and preserves immutable raw-source identity, checksums, deterministic derived data, and ignored generated artifacts.

## Target governance

Four documented UCI failure intervals are preserved as event metadata. Unverified rows are not converted into a verified healthy class. Chronological partitions, exclusion buffers, and gap-aware segment boundaries are enforced before modeling.

## Feature governance

The release uses the frozen 48-feature set derived from causal, partition-bounded and segment-bounded sensor history. Learned preprocessing was not fitted into the feature-engineering stage. Test rows do not influence feature definition.

## Evaluation governance

Training is used for fitting and threshold derivation, validation is used for candidate selection, and test is held out until the final one-time evaluation. The transparent robust-distance baseline was finalized before advanced-model development and is not revised from advanced-model evidence.
"""

    architecture = """# Machine-Learning Architecture

```text
Governed MetroPT-3 Source
        |
        v
Checksum + Schema + Data-Quality Validation
        |
        v
Parquet + DuckDB Analytical Layer
        |
        v
Gap-Aware Target Materialization
        |
        v
Causal 48-Feature Frozen Set
        |
        +------------------------------+
        |                              |
        v                              v
Transparent Robust-Distance       Isolation Forest
Baseline                          Frozen Candidate Grid
        |                              |
        v                              v
One-Time Baseline Test           Validation-Only Selection
Evidence                              |
                                       v
                               Frozen Selected Model
                                       |
                                       v
                            One-Time Held-Out Test Evidence
                                       |
                                       v
                            ML Release Documentation
```

The knowledge-retrieval, API, persistence, monitoring, Docker, and demonstration layers remain separate subsequent release milestones.
"""

    reproducibility = f"""# Machine-Learning Reproducibility

Run commands from the repository root with the project virtual environment active.

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m predictive_maintenance.analysis.isolation_forest_test_evaluation
python -m predictive_maintenance.analysis.ml_release_documentation
```

The one-time test command must **not** be rerun after its governed outputs exist. The evaluator intentionally refuses overwrite.

Frozen candidate: `{model['candidate_id']}`
Frozen threshold: `{model['threshold']}`
Model SHA-256: `{model['model_sha256']}`
"""

    readme = f"""# Intelligent Predictive Maintenance and Technical Knowledge Assistant

A professional AI engineering portfolio project that combines governed industrial time-series analysis, anomaly detection, and a planned citation-grounded technical-knowledge assistant.

## Current Verified Capability

The machine-learning foundation is complete through held-out evaluation. The repository includes reproducible MetroPT-3 acquisition and integrity checks, schema/data-quality validation, Parquet and DuckDB access, gap-aware exploratory analysis, governed event provenance and target materialization, causal feature engineering, a transparent robust-distance benchmark, and a bounded Isolation Forest comparison.

The selected advanced candidate is `{model['candidate_id']}` with frozen threshold `{model['threshold']}`. It was selected using validation evidence only and evaluated once on the locked test partition after explicit authorization. Test evidence did not change the model, feature set, or threshold.

## Machine-Learning Evaluation

| Measure | Isolation Forest | Robust-distance baseline |
|---|---:|---:|
| Documented-event coverage | {_fmt(adv['documented_event_coverage_fraction'])} | {_fmt(base['documented_event_coverage_fraction'])} |
| Mean first-alarm latency, covered events (s) | {_fmt(adv['mean_first_alarm_latency_seconds_for_covered_events'])} | {_fmt(base['mean_first_alarm_latency_seconds_for_covered_events'])} |
| Alarms per 24 observed hours | {_fmt(adv['alarms_per_24_observed_hours'])} | {_fmt(base['alarms_per_24_observed_hours'])} |

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
"""
    return {
        "docs/model_card.md": model_card,
        "docs/ml_evaluation_report.md": evaluation_report,
        "docs/data_feature_governance.md": governance,
        "docs/ml_architecture.md": architecture,
        "docs/ml_reproducibility.md": reproducibility,
        "README.md": readme,
    }


def write_documents(report_path: Path = DEFAULT_REPORT) -> list[Path]:
    report = _read_report(report_path)
    documents = build_documents(report)
    written: list[Path] = []
    for relative, content in documents.items():
        path = PROJECT_ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate frozen machine-learning release documentation.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    try:
        paths = write_documents(args.report)
    except (MLReleaseDocumentationError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps({"processing_status": "ml_release_documentation_generated", "files": [p.as_posix() for p in paths]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

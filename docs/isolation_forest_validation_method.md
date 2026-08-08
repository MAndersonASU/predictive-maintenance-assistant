# Governed Isolation Forest Training and Validation

> **Record status:** Implemented and frozen after validation. The selected candidate was subsequently evaluated once under the separately governed held-out protocol; this document preserves the validation-stage controls.

## Purpose

This workflow implements the bounded advanced-model comparison frozen before training. It evaluates exactly eight `sklearn.ensemble.IsolationForest` candidates and freezes one validation-selected candidate.

The finalized robust-distance baseline remains unchanged. Its held-out evidence is not used to design, tune, rank, or select an Isolation Forest candidate.

## Inputs and evidence chain

The workflow requires the frozen advanced-model comparison contract, governed feature/eligibility evidence, and the frozen robust-distance parameter file containing the ordered 48-feature set.

Input checks verify file existence, evidence status, Parquet checksums, train/validation timestamp alignment, feature presence and numeric type, reference-row count, and exact feature identity. Missing or non-finite model inputs stop execution.

## Candidate boundary

- `n_estimators`: 100 or 200
- `max_samples`: 1024 or 4096
- `max_features`: 0.5 or 1.0
- `contamination='auto'`
- `bootstrap=False`
- `random_state=42`
- `n_jobs=-1`

## Training, thresholding, and validation

Each candidate is fitted only on eligible training-reference rows. No learned scaling is fitted.

The anomaly score is `-IsolationForest.score_samples(X)`. The alarm threshold is the 0.995 quantile of that candidate's eligible training-reference scores and is frozen before validation. Validation alarms use `score > threshold`.

Only eligible validation rows are scored. Held-out rows are not used for feature selection, thresholding, or candidate ranking.

## Permitted validation evidence

The workflow records documented-event coverage, first-alarm latency, alarm contiguity, alarm burden, alarms per 24 observed hours, and training-versus-validation score-distribution summaries.

Alarm burden is not a false-positive rate. Unverified observations are not verified healthy negatives. Unsupported classification and failure-probability claims are not reported.

## Deterministic selection

Candidates are ranked by:

1. maximize documented-event coverage;
2. minimize mean first-alarm latency among covered events;
3. minimize alarms per 24 observed hours;
4. minimize candidate complexity rank.

The selected model, threshold, validation scores, and ranking are frozen in ignored generated artifacts.

## Generated artifacts

```text
outputs/metropt3_selected_isolation_forest.joblib
data/processed/metropt3_validation_isolation_forest.parquet
outputs/metropt3_isolation_forest_validation_report.json
```

## Held-out authorization boundary

At the time this validation decision was frozen, held-out comparison remained prohibited until the validation-decision checksum was recorded and separate explicit authorization for the one-time test evaluation was documented. That controlled one-time evaluation was later completed without refitting or reselection.

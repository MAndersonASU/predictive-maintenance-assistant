# Governed Isolation Forest Training and Validation

## Purpose

This workflow implements the bounded advanced-model comparison that was frozen before training. It evaluates exactly eight `sklearn.ensemble.IsolationForest` candidates and freezes one validation-selected candidate for a separately authorized future test evaluation.

The finalized robust-distance baseline remains unchanged. Its test evidence is not used to design, tune, rank, or select an Isolation Forest candidate.

## Inputs and evidence chain

The workflow requires:

- the frozen advanced-model comparison contract and its valid no-training report;
- the governed feature Parquet and feature-engineering evidence report;
- the governed baseline-eligibility Parquet and eligibility evidence report; and
- the frozen robust-distance parameter file, which supplies the exact ordered 48-feature set.

Input checks verify file existence, evidence status, Parquet checksums, train/validation timestamp alignment, feature presence and numeric type, the frozen reference-row count, and the exact 48-feature identity. Missing or non-finite model inputs stop execution before fitting.

## Candidate boundary

The only permitted family is Isolation Forest. The bounded grid is:

- `n_estimators`: 100 or 200;
- `max_samples`: 1024 or 4096; and
- `max_features`: 0.5 or 1.0.

Every candidate uses `contamination='auto'`, `bootstrap=False`, `random_state=42`, and `n_jobs=-1`. Candidate complexity rank is the ascending lexicographic order of `n_estimators`, `max_samples`, and `max_features`.

## Training, thresholding, and validation

Each candidate is fitted only on rows where `partition == 'train'` and `eligible_for_reference_fit` is true. No learned scaling or other preprocessing is fitted.

The anomaly score is `-IsolationForest.score_samples(X)`, so larger values are more unusual. The alarm threshold is the 0.995 quantile of that candidate's eligible training-reference scores. The threshold is frozen before validation. Validation alarms use a strict comparison: `score > threshold`.

Only rows where `partition == 'validation'` and `eligible_for_scoring` is true are scored. Test rows are not loaded, scored, counted as outcomes, or used for feature selection, thresholding, or candidate ranking.

## Permitted validation evidence

For each candidate, the workflow records:

- documented-event coverage;
- first-alarm latency for each covered documented event;
- longest contiguous alarm run within each documented event;
- alarm burden on the governed unlabeled burden population;
- alarms per 24 observed hours; and
- training-versus-validation score-distribution summaries.

Alarm burden is not reported as a false-positive rate. Unverified observations are not treated as verified healthy negatives. Accuracy, precision, specificity, ROC AUC, failure probability, and unsupported population sensitivity are not reported.

## Deterministic selection

Candidates are ranked lexicographically by:

1. maximize documented-event coverage;
2. minimize mean first-alarm latency among covered events;
3. minimize alarms per 24 observed hours; and
4. minimize candidate complexity rank.

The selected model, its training-derived threshold, its validation scores, and the complete ranking are frozen in ignored generated artifacts. A future one-time test comparison remains prohibited until the validation decision report checksum is recorded and the learner separately authorizes test access.

## Generated artifacts

The workflow writes the following ignored artifacts:

- `outputs/metropt3_selected_isolation_forest.joblib`;
- `data/processed/metropt3_validation_isolation_forest.parquet`; and
- `outputs/metropt3_isolation_forest_validation_report.json`.

The JSON report records input checksums, software versions, all eight candidate results, the selected candidate and threshold, output checksums, and explicit test-lock evidence.

## Execution

From the repository root with the virtual environment active and `PYTHONPATH=src`:

```powershell
python -m predictive_maintenance.analysis.isolation_forest_validation
```

Use `--overwrite` only when intentionally repeating the complete governed validation run before the decision is formally recorded. After the decision checksum is recorded, changing or overwriting the validation evidence requires a new governed authorization.

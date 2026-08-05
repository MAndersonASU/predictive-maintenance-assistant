# Frozen Robust-Distance Test Evaluation Method

## Purpose

This workflow performs the one-time governed test evaluation of the transparent MetroPT-3 robust-distance baseline. It loads the training-derived medians, interquartile ranges, retained-feature set, and threshold that were frozen before validation. It does not refit preprocessing, revise the threshold, or select a different baseline using test evidence.

## Required evidence chain

The evaluator requires the governed feature and eligibility Parquet files, their valid evidence reports, the frozen robust-distance parameter file, the completed validation report, and the validation-stage diagnostic report. Before reading the test scoring population, it verifies that:

- the parameter file still records `frozen_before_validation` and no prior test use;
- validation completed with zero test rows scored and the test partition locked;
- the diagnostic decision is `frozen_after_validation_diagnosis`;
- the selected quantile, numeric threshold, and retained-feature count match across the frozen evidence;
- feature and eligibility files have matching checksums, row counts, timestamps, and partition assignments.

## Score

For every retained feature, the evaluator applies the frozen robust transformation:

`absolute_robust_z = abs((value - training_median) / training_IQR)`

The row score is the maximum absolute robust z-score across all retained features. An alarm is produced only when the score is strictly greater than the frozen threshold.

## Test population

Only rows satisfying all of the following conditions are scored:

- feature partition is `test`;
- eligibility partition is `test`;
- `eligible_for_scoring` is true;
- every frozen retained feature is present and non-null.

The written score artifact contains no training or validation rows.

## Supported evidence

The final report records the test score distribution, documented-event coverage and first-alarm latency when governed test events are present, alarm burden on eligible unverified operational rows, and alarms per 24 observed hours.

Alarm burden is not a false-positive rate because unverified rows are not verified healthy negatives. Accuracy, precision, specificity, ROC AUC, and failure probability are not reported without the labels required to support those claims.

## Outputs

Generated artifacts remain outside Git under the existing governed ignore rules:

- `data/processed/metropt3_test_robust_distance.parquet`
- `outputs/metropt3_robust_distance_test_report.json`

Only the configuration, implementation, tests, and this method document are intended for version control.

## Reproducibility and decision boundary

A controlled `--overwrite` rerun may reproduce the same frozen evaluation after a failed or interrupted execution. It must not be used to change parameters, retained features, threshold, or interpretation after inspecting test results. Any later advanced-model comparison must be defined separately and must treat this transparent baseline result as fixed.

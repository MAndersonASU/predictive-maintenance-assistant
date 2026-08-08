# Frozen Robust-Distance Test Evaluation Method

> **Record status:** Implemented and consumed as the one-time held-out evaluation protocol for the transparent baseline. Subsequent advanced-model comparison does not alter this frozen result.

## Purpose

This workflow performs the one-time governed test evaluation of the transparent MetroPT-3 robust-distance baseline. It loads training-derived medians, interquartile ranges, retained features, and the threshold frozen before validation. It does not refit preprocessing, revise the threshold, or select a different baseline using test evidence.

## Required evidence chain

Before reading the test scoring population, the evaluator verifies frozen parameter status, zero prior test scoring in validation evidence, the frozen diagnostic decision, threshold/feature identity, and matching feature/eligibility checksums and timestamps.

## Score

For every retained feature:

`absolute_robust_z = abs((value - training_median) / training_IQR)`

The row score is the maximum absolute robust z-score across retained features. An alarm is produced only when the score is strictly greater than the frozen threshold.

## Test population

Only rows in the chronological `test` partition with `eligible_for_scoring = true` and complete retained-feature values are scored. The score artifact contains no training or validation rows.

## Supported evidence

The final report records test score distribution, documented-event coverage, first-alarm latency, alarm burden on eligible unverified observations, and alarms per 24 observed hours.

Alarm burden is not a false-positive rate because unverified rows are not verified healthy negatives. Unsupported classification and failure-probability claims are not reported.

## Outputs

```text
data/processed/metropt3_test_robust_distance.parquet
outputs/metropt3_robust_distance_test_report.json
```

Generated artifacts remain outside Git.

## Reproducibility and decision boundary

A controlled `--overwrite` rerun may reproduce the same frozen evaluation only when required for failed/interrupted execution recovery. It must not be used to change parameters, features, threshold, or interpretation after inspecting test results. The later advanced-model comparison treats this transparent baseline result as fixed.

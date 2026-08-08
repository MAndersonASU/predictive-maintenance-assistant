# Isolation Forest One-Time Test Evaluation Method

> **Record status:** Implemented and consumed exactly once for the frozen selected Isolation Forest release. Successful outputs are protected against overwrite.

## Purpose

This stage consumes the separately authorized advanced-model held-out access exactly once. It evaluates only the Isolation Forest candidate frozen after validation.

## Frozen inputs

- Candidate: `iforest_ne200_ms4096_mf1p0`
- Threshold: `0.601902290159477`
- Feature count: 48
- Model artifact: `outputs/metropt3_selected_isolation_forest.joblib`
- Held-out partition: locked until this evaluation stage

The evaluator validates the model SHA-256 against the frozen Isolation Forest validation report and verifies the frozen feature identity before scoring.

## Test-time prohibitions

The evaluator cannot fit or refit the model, revise the threshold, change features, expand the model family, reselect a candidate, label unverified rows as healthy, interpret alarm burden as false-positive rate, or interpret unusualness as failure probability.

## Evidence

Only eligible rows in the chronological `test` partition are scored. Documented-event coverage, first-alarm latency, alarm burden, score summaries, and a transparent comparison with the finalized robust-distance baseline are recorded.

The comparison is reporting evidence only. Held-out evidence does not authorize model changes.

## One-time lock

Successful outputs are never overwritten. If either final test output already exists, the command refuses to run again.

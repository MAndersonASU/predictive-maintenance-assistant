# Isolation Forest One-Time Test Evaluation Method

## Purpose

This stage consumes the separately authorized advanced-model test access exactly once. It evaluates only the Isolation Forest candidate frozen after validation.

## Frozen inputs

- Candidate: `iforest_ne200_ms4096_mf1p0`
- Threshold: `0.601902290159477`
- Feature count: 48
- Model artifact: `outputs/metropt3_selected_isolation_forest.joblib`
- Test partition: locked until this stage

The evaluator validates the model SHA-256 against the Day 16 validation report and validates the frozen feature identity before test scoring.

## Test-time prohibitions

The evaluator cannot fit or refit the model, revise the threshold, change features, expand the model family, reselect a candidate, label unverified rows as healthy, interpret alarm burden as false-positive rate, or interpret unusualness as failure probability.

## Evidence

Only rows in the chronological `test` partition that are marked `eligible_for_scoring` are scored. Documented-event coverage, first-alarm latency for covered events, alarm burden, score summaries, and a transparent comparison with the already-finalized robust-distance baseline are recorded.

The comparison is reporting evidence only. Test evidence does not authorize model changes.

## One-time lock

Successful outputs are never overwritten. If either final test output already exists, the command refuses to run again.

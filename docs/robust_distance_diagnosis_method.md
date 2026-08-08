# Frozen Robust-Distance Baseline Diagnosis

> **Record status:** Implemented validation-stage diagnostic specification. The transparent baseline was subsequently evaluated once on held-out evidence; this document preserves the diagnostic controls used before that evaluation.

## Purpose

This analysis diagnoses the already-frozen robust-distance baseline using eligible training-reference and validation evidence only. It does not refit feature medians or interquartile ranges, does not use validation to learn parameters, and does not read the test partition into the diagnostic population.

## Diagnostic questions

1. Which retained feature most often supplies the maximum absolute robust contribution?
2. Which features have very small but nonzero training IQRs and may amplify small deviations?
3. How concentrated are validation alarms by observation segment, operating state, and hour of day?
4. How do the May 29 delayed detection and June 5 missed event change under three training-derived threshold candidates?
5. Which transparent baseline threshold is frozen after validation diagnosis?

## Method

For feature `j`, the frozen contribution at row `t` is:

`c[t,j] = abs((x[t,j] - median[j]) / IQR[j])`

The row score is the largest feature contribution. The bounded threshold candidates are the 0.990, 0.995, and 0.999 quantiles of eligible training-reference scores. Validation evidence can compare those candidates but cannot create a validation-fitted threshold.

## Operating-state analysis

An operating state is the ordered eight-value signature formed from `COMP`, `DV_eletric`, `Towers`, `MPG`, `LPS`, `Pressure_switch`, `Oil_level`, and `Caudal_impulses`. For each observed validation state, the report records scored rows, eligible alarm-burden rows, alarm rows, and burden fraction.

Fractions from rare states are descriptive only and must not be interpreted as stable risk estimates.

## Governance

- Frozen robust-distance validation parameters are inputs, not refitted values.
- Candidate thresholds come only from eligible training-reference scores.
- Validation is used for diagnosis; the held-out partition was locked during this diagnostic stage.
- Unverified rows are not treated as verified healthy negatives.
- Alarm burden is not a false-positive rate.
- Operating-state alarm burden is not failure probability or causal evidence.
- Unsupported classification metrics are not reported.

## Outputs

The ignored JSON report records checksums, row counts, dominant features, small-IQR evidence, alarm concentration, threshold-candidate evidence, documented-event coverage/latency, the frozen baseline decision, and limitations.

```text
outputs/metropt3_robust_distance_diagnostic_report.json
```

## Reproduction

```powershell
python -m predictive_maintenance.analysis.robust_distance_diagnosis
```

Use `--overwrite` only when intentionally regenerating the ignored diagnostic report from the same governed inputs.

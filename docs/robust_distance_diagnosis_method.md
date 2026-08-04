# Frozen Robust-Distance Baseline Diagnosis

## Purpose

This analysis diagnoses the already-frozen robust-distance baseline using eligible training-reference and validation evidence only. It does not refit feature medians or interquartile ranges, does not use validation to learn parameters, and does not read the test partition into the diagnostic population.

## Diagnostic questions

The report answers five bounded questions:

1. Which retained feature most often supplies the maximum absolute robust contribution?
2. Which features have very small but nonzero training IQRs and may amplify small deviations?
3. How concentrated are validation alarms by observation segment, operating state, and hour of day?
4. How do the May 29 delayed detection and June 5 missed event change under three training-derived threshold candidates?
5. Which transparent baseline threshold is frozen after validation diagnosis?

## Method

For feature $j$, the frozen contribution at row $t$ is

$$
c_{t,j}=\left|\frac{x_{t,j}-m_j}{IQR_j}\right|,
$$

where $m_j$ and $IQR_j$ were fitted previously on eligible training-reference rows. The row score is the largest feature contribution. The dominant feature is the feature that supplies that maximum.

The bounded threshold candidates are the 0.990, 0.995, and 0.999 quantiles of scores from eligible training-reference rows. Validation evidence can compare those candidates, but it cannot create a validation-fitted threshold. The configured selection remains 0.995 unless the governed configuration is intentionally reviewed and changed before test access.

## Operating-state analysis

An operating state is the ordered eight-value signature formed from `COMP`, `DV_eletric`, `Towers`, `MPG`, `LPS`, `Pressure_switch`, `Oil_level`, and `Caudal_impulses`. The ordered feature list is stored in the diagnostic configuration so the grouping is reproducible.

For every observed validation scoring state, the report records scored rows, rows eligible for alarm-burden analysis, alarm rows within that burden population, and the corresponding alarm-burden fraction. State results are ordered by alarm count and then burden-population size. Fractions from rare states are descriptive only and must not be interpreted as stable state-risk estimates.

## Governance

- Frozen Day 12 parameters are inputs, not refitted values.
- Candidate thresholds come only from eligible training-reference scores.
- Validation is used for diagnosis; test remains locked.
- Unverified rows are not treated as verified healthy negatives.
- Alarm burden is not reported as a false-positive rate.
- Operating-state alarm burden is not failure probability or causal evidence.
- The analysis does not report accuracy, precision, specificity, ROC AUC, or failure probability.

## Outputs

The ignored JSON report records input checksums, row counts, dominant features, small-IQR evidence, alarm concentration by segment, operating state, and UTC hour, threshold-candidate evidence, event coverage and latency, the frozen baseline decision, and limitations. The report is written to `outputs/metropt3_robust_distance_diagnostic_report.json`.

## Reproduction

Run from the repository root with the project virtual environment active:

```powershell
python -m predictive_maintenance.analysis.robust_distance_diagnosis
```

Use `--overwrite` only when intentionally regenerating the ignored diagnostic report from the same governed inputs.

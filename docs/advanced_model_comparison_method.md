# Governed Advanced-Model Comparison Contract

## Purpose

This method defines the comparison rules that must be validated before an advanced anomaly model is fitted. It preserves the finalized robust-distance baseline as a transparent reference, blocks test-driven design, bounds the candidate search, and records a deterministic validation-selection rule.

The contract-validation step does **not** fit preprocessing, train an advanced model, generate scores or alarms, select a candidate, or access the advanced-model test partition.

## Finalized baseline boundary

The robust-distance baseline is frozen at commit `1b03c4ae695e04da1f03304f7154b35f1da92d1a`. Its 48 retained features, 0.995 training-score threshold quantile, and threshold `7857.013759410036` cannot be revised.

The finalized baseline test report is preserved by its expected SHA-256. Its results are prohibited from candidate design, feature selection, preprocessing decisions, hyperparameter selection, threshold selection, or validation ranking. The report may serve only as a reference after the advanced method and validation decision are frozen.

## Governed population

Advanced-model development is restricted to the existing eligibility evidence:

- Fit population: rows where `eligible_for_reference_fit` is true in the `train` partition.
- Validation scoring: rows where `eligible_for_scoring` is true in the `validation` partition.
- Known-event evidence: validation rows where `eligible_for_known_event_evaluation` is true.
- Alarm-burden evidence: validation rows where `eligible_for_alarm_burden` is true.
- Test partition: locked.

Unverified operational rows remain unlabeled. They are not converted into verified healthy negatives. Chronological, segment-safe, partition-bounded, exclusion, and complete-history controls remain mandatory.

## Bounded candidate family

The only candidate family authorized by this contract is `sklearn.ensemble.IsolationForest`, used for unsupervised anomaly scoring.

Every candidate must use the same frozen 48-feature set retained by the robust-distance baseline. Missing or non-finite eligible inputs must stop fitting. No validation- or test-fitted preprocessing is allowed, and scaling is disabled for this bounded comparison.

Fixed parameters:

- `contamination="auto"`
- `bootstrap=False`
- `random_state=42`
- `n_jobs=-1`

Bounded grid:

| Parameter | Allowed values |
|---|---|
| `n_estimators` | 100, 200 |
| `max_samples` | 1024, 4096 |
| `max_features` | 0.5, 1.0 |

The Cartesian product contains exactly eight candidates. Adding a family, parameter, or value requires a new governed contract rather than an informal expansion.

## Score and threshold

Candidate unusualness is defined as the negative of `score_samples`, so larger values mean more unusual behavior. Each candidate threshold is the 0.995 quantile of that candidate's eligible training-reference scores. The threshold is frozen before validation; validation and test threshold tuning are prohibited.

The score is an unusualness score. It is not a failure probability.

## Deterministic validation selection

Candidates are ranked lexicographically on validation evidence only:

1. Maximize documented-event coverage.
2. Minimize mean first-alarm latency among covered documented events.
3. Minimize alarms per 24 observed hours.
4. Minimize deterministic candidate-complexity rank using `n_estimators`, then `max_samples`, then `max_features`.

Supported evidence includes documented-event coverage, first-alarm latency, alarm contiguity, alarm burden, alarms per 24 observed hours, and score-distribution drift. Alarm burden is not a false-positive rate.

Accuracy, precision, population sensitivity, specificity, false-positive rate, ROC AUC, and failure-probability claims remain unsupported because the operational reference population is not a verified healthy negative class.

## Test lock

The advanced-model test partition remains locked until all six conditions are verified:

1. The comparison contract is validated.
2. The candidate implementation is tested.
3. The full bounded grid is evaluated on validation only.
4. The winning candidate and threshold are frozen.
5. The validation-decision report is checksummed.
6. Separate explicit authorization is received for the one-time advanced-model test evaluation.

The finalized baseline test evidence cannot select the advanced candidate. After the advanced method is frozen, a future one-time test evaluation may compare the frozen advanced result with the preserved baseline reference.

## Contract validation

Run from the repository root with the virtual environment active and `PYTHONPATH` set to `src`:

```powershell
$env:PYTHONPATH = "src"
python -m predictive_maintenance.analysis.advanced_model_comparison
```

The validator checks the contract, verifies all baseline source and generated evidence files are present, confirms the finalized baseline test-report checksum, and writes:

```text
outputs/metropt3_advanced_model_comparison_contract_report.json
```

The report records evidence checksums, candidate bounds, selection order, test-lock conditions, and explicit no-training scope. The generated report remains outside Git under the repository's governed output-ignore rules.

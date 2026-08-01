# MetroPT-3 Feature-Engineering Method

## Purpose

This workflow converts the governed MetroPT-3 sensor history and verified target-state table into reproducible feature rows. It creates model inputs only. It does not create a healthy negative class, fit learned preprocessing, train a model, or report performance.

## Declared feature contract

The committed JSON contract is the authority for feature names and behavior. The seven continuous signals and eight operating-state signals are preserved as current values. Each continuous signal also receives:

- a one-row lag;
- a one-row difference;
- causal 6-row mean and population standard deviation;
- causal 30-row mean and population standard deviation.

At the verified 10-second sampling interval, 6 and 30 rows nominally represent one and five minutes. They remain row windows rather than elapsed-time promises because missing observations can exist.

## Leakage and gap controls

All lag and rolling calculations use the current row and earlier rows only. History resets whenever `segment_id` changes or chronological `partition` changes, including entry to and exit from an excluded partition buffer. The first row of every history group therefore has a null lag and difference. Partial rolling windows are retained and made auditable through `history_rows_available`, `has_lag_1_history`, `has_full_6_row_history`, and `has_full_30_row_history`.

The unnamed source row identifier is excluded because it has no declared operational meaning. No backward fill, centered window, or future-derived statistic is allowed.

## Governance preservation

The output preserves `timestamp`, `segment_id`, `partition`, `target_state`, `binary_target`, `source_event`, and `exclusion_reason`. Feature availability does not change target eligibility: `unverified` remains unverified and excluded rows remain excluded.

Learned preprocessing is explicitly disabled in this milestone. If a later milestone enables a scaler, imputer, selector, or encoder, its parameters must be fitted only on eligible training rows and then applied unchanged to validation and test rows.

## Validation and evidence

Before writing output, the workflow verifies both Parquet SHA-256 values, required schemas, non-empty equal row counts, and identical timestamp sets. It writes Parquet and JSON atomically, records input and output checksums, row and column counts, segment and history-group counts, target and partition counts, software versions, and scope exclusions. Generated data and reports remain ignored by Git under the repository's existing rules.

## Bounded endpoint

This milestone ends when the configured pipeline, controlled tests, generated feature Parquet, and evidence report are verified and synchronized with the public repository. Model training, model comparison, and performance reporting remain outside this milestone.

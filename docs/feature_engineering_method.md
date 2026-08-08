# MetroPT-3 Feature-Engineering Method

> **Record status:** Implemented engineering specification. The feature set described here is the governed upstream basis for the frozen machine-learning release.

## Purpose

This workflow converts governed MetroPT-3 sensor history and target states into reproducible model inputs. It does not create a healthy negative class, fit learned preprocessing, train a model, or report performance.

## Declared feature contract

The committed JSON contract is authoritative for feature names and behavior. Seven continuous signals and eight operating-state signals are preserved as current values. Each continuous signal also receives:

- one-row lag;
- one-row difference;
- causal 6-row mean and population standard deviation;
- causal 30-row mean and population standard deviation.

At the verified 10-second sampling interval, 6 and 30 rows nominally represent one and five minutes. They remain row windows rather than elapsed-time guarantees because missing observations can exist.

## Leakage and gap controls

Lag and rolling calculations use the current row and earlier rows only. History resets whenever `segment_id` or chronological `partition` changes. Partial history is exposed through `history_rows_available`, `has_lag_1_history`, `has_full_6_row_history`, and `has_full_30_row_history`.

The unnamed source row identifier is excluded because it has no declared operational meaning. No backward fill, centered window, or future-derived statistic is allowed.

## Governance preservation

The output preserves `timestamp`, `segment_id`, `partition`, `target_state`, `binary_target`, `source_event`, and `exclusion_reason`. Feature availability does not change target eligibility: `unverified` remains unverified and excluded rows remain excluded.

Learned preprocessing is disabled in this component. Any future fitted transformation must be learned only on eligible training rows and applied unchanged to validation and test rows.

## Validation and evidence

Before writing output, the workflow verifies input Parquet checksums, required schemas, non-empty equal row counts, and identical timestamp sets. It writes Parquet and JSON atomically and records checksums, row/column counts, segment/history counts, target/partition counts, software versions, and scope exclusions.

## Component boundary

Feature creation is intentionally separated from model fitting and performance evaluation. Downstream model components consume this governed feature contract without redefining it.

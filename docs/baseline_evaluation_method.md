# MetroPT-3 Baseline and Temporal-Evaluation Contract

> **Record status:** Implemented historical contract. The transparent robust-distance baseline and later advanced-model evaluation were implemented under these frozen controls; the contract remains authoritative for population and metric semantics.

## Purpose

This contract defines who may establish the transparent anomaly reference, how later observations may be scored, and which evaluation statements the available evidence can support. The validation workflow materializes row-level eligibility evidence only.

## Target interpretation

The dataset contains documented failure intervals but no verified healthy-negative class. A row with `target_state = unverified` is an unlabeled operational observation, not a confirmed normal or negative example. Documented-failure rows are verified positives for event-oriented evaluation. Pre-event exclusions, chronological partition buffers, incomplete 30-row histories, and rows with exclusion reasons are ineligible.

The reference population is restricted to eligible `unverified` rows in the training partition. It represents the observed training-period operating mixture; contamination by unrecorded abnormal behavior remains possible.

## Transparent baseline contract

The governed baseline fits each numeric feature's median and interquartile range on eligible training-reference rows only. Features with zero interquartile range are excluded with a recorded reason. Frozen parameters are applied unchanged to validation and test rows.

The score is the maximum absolute robust z-score across retained features. It is unusualness relative to the unlabeled training reference, not a failure probability. The threshold uses the 99.5th percentile of eligible training-reference scores and is frozen before validation.

## Temporal and segment controls

Training precedes validation, and validation precedes test. Random splitting is prohibited. Eligible rows require complete causal history inside one segment and partition. No fitted parameter, feature history, threshold choice, or evaluation relationship may leak backward from a later partition.

## Supported evaluation language

Documented events support event coverage, first-alarm latency, and alarm contiguity within recorded event intervals. Unlabeled operating periods support alarm burden, alarms per 24 observed hours, and score-distribution drift.

Alarm burden is operational review load, not a false-positive rate. Accuracy, precision, specificity, false-positive rate, ROC AUC, calibrated failure probability, and verified healthy-class claims are unsupported.

## Validation evidence

The workflow verifies feature identity, Parquet checksums, governance columns, row counts, target consistency, non-empty eligibility populations, and chronological ordering. It writes ignored eligibility Parquet and JSON evidence atomically.

## Contract boundary

This file governs eligibility, leakage controls, baseline semantics, and supported metrics. Baseline fitting, diagnosis, held-out evaluation, and advanced-model comparison are implemented as separate governed components.

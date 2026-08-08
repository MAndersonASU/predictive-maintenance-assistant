# MetroPT-3 Transparent Robust-Distance Baseline

> **Record status:** Implemented validation-stage specification. The baseline was subsequently evaluated once on governed held-out evidence and remains the transparent benchmark.

## Purpose

This implementation establishes a transparent anomaly score relative to the eligible unlabeled training-reference population. It does not infer a verified healthy class or a probability of failure. At this validation stage, the test partition remained locked.

## Frozen training-reference fit

For every numeric model feature, the workflow fits the median and interquartile range (IQR) using only rows marked `eligible_for_reference_fit` in the training partition. A zero-IQR feature is excluded with a recorded reason.

For retained feature `j`, the robust distance component is the absolute difference from the training median divided by the training IQR. A row's score is the maximum component across retained features. The alarm threshold is the 99.5th percentile of scores from the same eligible training-reference population. Medians, IQRs, exclusions, and threshold are frozen before validation.

## Validation and test boundary

Frozen parameters are applied to eligible validation rows. The validation score file contains no test rows. The implementation reports score summaries, documented-event coverage, first-alarm latency, alarm burden over unlabeled validation observations, and alarms per 24 observed hours.

Alarm burden is operational review load, not a false-positive rate. Unverified observations are not confirmed healthy negatives.

## Reproducibility and evidence

The workflow verifies upstream feature and eligibility checksums, matching timestamps and row counts, atomic outputs, and output checksums. Generated parameters, validation scores, and reports remain ignored artifacts.

## Component boundary

This file describes the validation-stage robust-distance implementation. Held-out evaluation, advanced-model comparison, and the frozen release decision are documented in their respective components and do not alter this baseline fitting contract.

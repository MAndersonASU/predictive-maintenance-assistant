# MetroPT-3 Transparent Robust-Distance Baseline

## Purpose

This implementation establishes a transparent anomaly score relative to the eligible unlabeled training-reference population. It does not infer a verified healthy class or a probability of failure. The test partition remains locked.

## Frozen training-reference fit

For every numeric model feature, the workflow fits the median and interquartile range (IQR) using only rows marked `eligible_for_reference_fit` in the training partition. A feature with zero IQR cannot provide a scaled distance, so it is excluded and recorded with the reason `zero_iqr_in_eligible_training_reference`.

For retained feature $j$, the robust distance component is the absolute difference from the training median divided by the training IQR. A row's score is the maximum component across retained features. The alarm threshold is the 99.5th percentile of scores from the same eligible training-reference population. The fitted medians, IQRs, exclusions, and threshold are frozen before validation.

## Validation and test lock

The frozen parameters are applied only to eligible validation rows. The generated score file contains validation rows and no test rows. The implementation reports the number of scored validation rows, training and validation score summaries, documented-event coverage, first-alarm latency, alarm burden over unlabeled validation observations, and alarms per 24 observed hours.

Alarm burden is operational review load, not a false-positive rate. Unverified observations are not confirmed healthy negatives, so accuracy, precision, specificity, false-positive rate, and ROC AUC remain unsupported.

## Reproducibility and evidence

The workflow verifies the upstream feature and eligibility Parquet checksums against their evidence reports, confirms matching timestamps and row counts, writes outputs atomically, and records output checksums. Generated parameters, validation scores, and reports remain ignored artifacts. The committed source files define the reproducible method and its controlled tests.

## Bounded endpoint

This milestone ends after the configuration, implementation, tests, generated validation evidence, documentation, and repository synchronization are verified. Test evaluation, model comparison, advanced models, deployment, and performance claims remain outside this milestone.

# Target Definition and Temporal Evaluation Method

## Purpose

This method defines how the MetroPT-3 project records documented failure-event
metadata, optional prediction windows, source conflicts, and chronological
evaluation boundaries before any row-level labels, predictive features, or
models are created.

## Evidence hierarchy

A proposed event must identify its source title, source type, persistent source
identifier, exact locator, access date, dataset match, interpretation,
confidence, and any unresolved source conflicts.

A `documented` event must come from an exact match to the governed dataset.
Related papers can provide domain context but cannot silently replace the
failure records belonging to another dataset version or collection period.
Sensor rarity, visual patterns, and exploratory statistics remain supporting
evidence only and must not be converted directly into failure labels.

## Governed MetroPT-3 source

The exact source used for the current event records is:

- UCI Machine Learning Repository, **MetroPT-3 Dataset**
- DOI: `10.24432/C5VW3R`
- Dataset coverage: February through August 2020
- Repository access date used in the configuration: July 30, 2026

The UCI page states that the dataset is unlabeled and separately provides a
Failure Information table. The four intervals in the governed configuration
are therefore event metadata. They are not an existing target column and are
not yet row-level labels.

## Interval semantics

- **Observed failure interval:** documented period in which the source reports a malfunction.
- **Prediction window:** optional earlier period derived from a justified alerting policy.
- **Ambiguous period:** interval with insufficient evidence; excluded rather than forced into a class.
- **Unlabeled period:** not automatically treated as verified healthy operation.

The schema does not require a prediction window for every documented event.
This prevents a verified source interval from forcing an invented warning
window. When a prediction window is later added, the validator requires it to
end before the event and preserve the configured minimum warning time.

## Source-conflict preservation

The UCI entry beginning May 29, 2020 includes the note `Maintenance on 30Apr at
12:00`, which conflicts with the May 29-30 event dates. The configuration keeps
this statement as an unresolved source conflict. It is not silently corrected,
interpreted as April 30, or used to change the event interval.

## Leakage controls

Evaluation partitions are strictly chronological. Training precedes validation,
which precedes testing, and a temporal buffer separates each boundary.

All later rolling windows, lagged values, labels, and features must remain
inside one verified observation segment. No calculation may cross any of the
363 known temporal gaps. Scaling, imputation, threshold learning, feature
selection, and other fitted transformations must use training data only.

## Current scope

The implemented validator checks the governed design specification only. It
does not:

- assign labels to MetroPT-3 rows;
- invent prediction windows;
- assume unlabeled rows are healthy;
- engineer features or create model-ready datasets;
- train or evaluate models;
- publish performance metrics.

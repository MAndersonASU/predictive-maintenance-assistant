# Target Definition and Temporal Evaluation Method

> **Record status:** Implemented engineering specification preserved as the source contract for event governance. Row-level target materialization and downstream model work are implemented separately.

## Purpose

This method defines how the MetroPT-3 project records documented failure-event metadata, optional prediction windows, source conflicts, and chronological evaluation boundaries without manufacturing unsupported labels.

## Evidence hierarchy

A proposed event must identify its source title, source type, persistent source identifier, exact locator, access date, dataset match, interpretation, confidence, and any unresolved source conflicts.

A `documented` event must come from an exact match to the governed dataset. Related papers can provide domain context but cannot silently replace the failure records belonging to another dataset version or collection period. Sensor rarity, visual patterns, and exploratory statistics remain supporting evidence only and must not be converted directly into failure labels.

## Governed MetroPT-3 source

- UCI Machine Learning Repository, **MetroPT-3 Dataset**
- DOI: `10.24432/C5VW3R`
- Dataset coverage: February through August 2020
- Repository access date recorded in configuration: July 30, 2026

The UCI source describes MetroPT-3 as unlabeled and provides failure reports separately. The four governed intervals are therefore event metadata. Row-level states are materialized separately by `target_materialization.py`.

## Interval semantics

- **Observed failure interval:** documented period in which the source reports a malfunction.
- **Prediction window:** optional earlier period derived from a justified alerting policy.
- **Ambiguous period:** interval with insufficient evidence; excluded rather than forced into a class.
- **Unlabeled period:** not automatically treated as verified healthy operation.

The schema does not require a prediction window for every documented event. This prevents a verified source interval from forcing an invented warning window.

## Source-conflict preservation

The UCI entry beginning May 29, 2020 includes the note `Maintenance on 30Apr at 12:00`, which conflicts with the May 29-30 event dates. The configuration keeps this statement as an unresolved source conflict. It is not silently corrected, interpreted as April 30, or used to change the event interval.

## Leakage controls

Evaluation partitions are strictly chronological. Training precedes validation, which precedes testing, and a temporal buffer separates each boundary.

Rolling windows, lagged values, labels, and features must remain inside one verified observation segment. No calculation may cross any of the 363 known temporal gaps. Scaling, imputation, threshold learning, feature selection, and other fitted transformations must use training data only.

## Contract scope

This validator governs event meaning, provenance, conflicts, and temporal evaluation boundaries. It does not itself assign row-level states, engineer features, train models, or publish performance metrics. Those downstream responsibilities are implemented in separate governed modules.

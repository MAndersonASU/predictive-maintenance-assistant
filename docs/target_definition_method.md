# Target Definition and Temporal Evaluation Method

## Purpose

This method defines how the MetroPT-3 project will document failure events,
prediction windows, ambiguous periods, and chronological evaluation boundaries
before any row-level labels, predictive features, or models are created.

## Evidence hierarchy

A proposed event must identify its source, source type, exact locator,
interpretation, and confidence. Exact maintenance records and the governed
dataset paper take priority. Sensor rarity, visual patterns, and exploratory
statistics are supporting evidence only and must not be converted directly
into failure labels.

## Interval semantics

- **Observed failure interval:** documented period in which the malfunction occurred.
- **Prediction window:** earlier period in which an alert would still be useful.
- **Ambiguous period:** interval with insufficient evidence; excluded rather than forced into a class.
- **Unlabeled period:** not automatically treated as verified healthy operation.

The initial policy requires at least two hours between the end of a prediction
window and the start of its observed failure interval unless a later governed
operational requirement replaces that value.

## Leakage controls

Evaluation partitions are strictly chronological. Training precedes validation,
which precedes testing. A temporal buffer separates each boundary.

All later rolling windows, lagged values, labels, and features must remain
inside one verified observation segment. No calculation may cross any of the
363 known temporal gaps. Scaling, imputation, threshold learning, feature
selection, and other fitted transformations must use training data only.

## Current scope

The implemented validator checks the design specification only. It does not:

- assign labels to MetroPT-3 rows;
- assert that placeholder event timestamps are verified;
- engineer features;
- create model-ready datasets;
- train or evaluate models;
- publish performance metrics.

Exact event intervals must be confirmed from governed source documentation
before the configuration can support row-level labeling.

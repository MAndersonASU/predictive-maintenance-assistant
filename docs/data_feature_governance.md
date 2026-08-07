# Data and Feature Governance Summary

## Data identity

The machine-learning workstream uses the governed MetroPT-3 Air Production Unit compressor dataset and preserves immutable raw-source identity, checksums, deterministic derived data, and ignored generated artifacts.

## Target governance

Four documented UCI failure intervals are preserved as event metadata. Unverified rows are not converted into a verified healthy class. Chronological partitions, exclusion buffers, and gap-aware segment boundaries are enforced before modeling.

## Feature governance

The release uses the frozen 48-feature set derived from causal, partition-bounded and segment-bounded sensor history. Learned preprocessing was not fitted into the feature-engineering stage. Test rows do not influence feature definition.

## Evaluation governance

Training is used for fitting and threshold derivation, validation is used for candidate selection, and test is held out until the final one-time evaluation. The transparent robust-distance baseline was finalized before advanced-model development and is not revised from advanced-model evidence.

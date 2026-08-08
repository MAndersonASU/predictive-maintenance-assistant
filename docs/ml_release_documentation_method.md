# Machine-Learning Release Documentation Method

## Purpose

The release-documentation generator converts only frozen machine-learning evidence into ML-specific public repository documentation.

Generated committed artifacts:

- `docs/model_card.md`
- `docs/ml_evaluation_report.md`
- `docs/data_feature_governance.md`
- `docs/ml_architecture.md`
- `docs/ml_reproducibility.md`

The generator intentionally does **not** generate `README.md` or the integrated system architecture. Those repository-level documents span machine learning, governed technical knowledge, retrieval, grounding, and later application layers and therefore must not be overwritten by an ML-only evidence generator.

The generator does not perform model selection or modify generated evaluation evidence. Historical engineering-log finalization is handled separately and must not overwrite the repository's current cross-workstream status.

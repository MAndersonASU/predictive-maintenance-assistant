# Machine-Learning Release Documentation Method

The release-documentation generator reads only the frozen one-time Isolation Forest test report and converts verified evidence into public repository documentation.

Generated committed artifacts:

- `docs/model_card.md`
- `docs/ml_evaluation_report.md`
- `docs/data_feature_governance.md`
- `docs/ml_architecture.md`
- `docs/ml_reproducibility.md`
- `README.md`

The generator does not perform model selection or modify generated evaluation evidence. The engineering log is finalized separately after the implementation commit exists so that the exact commit SHA and authoritative complete-test count can be recorded without fabrication.

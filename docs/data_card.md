# Data Card — MetroPT-3 Governed Release

## Dataset and purpose

This project uses the UCI MetroPT-3 Air Production Unit dataset to develop and evaluate a bounded anomaly-detection workflow for compressor observations. The data supports engineering analysis and portfolio demonstration; it does not establish a verified healthy population, a safety system, or equipment-specific maintenance instructions.

## Identity and provenance

- Source: UCI Machine Learning Repository, MetroPT-3 Dataset.
- Governed raw file: `MetroPT3(AirCompressor).csv`.
- Observations: 1,516,948 timestamped rows.
- Columns: 17, including the timestamp and 16 sensor/state signals.
- Source identity, retrieval metadata, license information, and SHA-256 are recorded in `data/source_manifest.csv` and validated by the acquisition pipeline.
- Raw, interim, and processed data remain generated local artifacts and are excluded from Git.

## Known data conditions

The repository validates schema, timestamp parsing, duplicate behavior, missing values, sensor types, and temporal coverage before analysis. The observed timeline contains 363 gaps greater than the nominal sampling interval; the largest is 172,918 seconds. Analysis and feature generation therefore use gap-aware segments instead of treating the full file as one continuous series.

Four documented UCI failure intervals are preserved as event metadata. Rows outside those intervals are unverified operational observations, not verified healthy negatives.

## Transformations

1. The raw source is acquired with immutable identity and checksum controls.
2. Schema and data-quality checks run before conversion.
3. A deterministic Parquet representation supports selective DuckDB analysis.
4. Chronological train, validation, and test partitions are created with exclusion buffers.
5. Causal rolling and state features are computed only from prior rows inside the same partition and temporal segment.
6. The released model consumes a frozen 48-feature schema.

Learned preprocessing is not fitted during feature generation. Test rows do not influence feature definition, fitting, threshold derivation, or candidate selection.

## Evaluation use

Training data supports model fitting and threshold derivation. Validation data supports the bounded eight-candidate Isolation Forest comparison. The test partition was accessed once for final reporting after the model, features, and threshold were frozen. Held-out evidence cannot be reused for retuning this release.

## Appropriate use

- Reproduce the governed analytical and anomaly-detection workflow.
- Inspect operational unusualness and review burden under the documented protocol.
- Demonstrate leakage controls, artifact identity, testing, and engineering traceability.

## Inappropriate use

- Treat unverified rows as confirmed healthy examples.
- Interpret unusualness as failure probability.
- Report alarm burden as a false-positive rate.
- Generalize the measured results to other compressors or operating environments.
- Use the project as a safety controller or a replacement for qualified equipment inspection.

## Related evidence

- `docs/data_feature_governance.md`
- `docs/failure_event_provenance.md`
- `docs/feature_engineering_method.md`
- `docs/model_card.md`
- `docs/evaluation_summary.md`

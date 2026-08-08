# Governed Row-Level Target-State Materialization

> **Record status:** Implemented engineering specification. Downstream causal feature engineering and model evaluation are implemented separately; this document remains the authority for row-state semantics.

## Purpose

This method converts the four documented MetroPT-3 failure intervals into an auditable row-state table. It preserves uncertainty instead of manufacturing a binary classification dataset before trustworthy negative examples exist.

## State policy

Each timestamp receives exactly one state:

- `documented_failure`: timestamp inside one of the four exact UCI failure intervals; `binary_target` is `1`.
- `excluded_pre_event`: timestamp within the two-hour buffer immediately before an event and in the same observation segment.
- `excluded_partition_buffer`: timestamp between governed train, validation, and test partitions.
- `unverified`: no documented failure or exclusion evidence; not interpreted as healthy and assigned a null binary target.
- `warning_not_enabled`: reserved in the schema but not assigned because the evidence does not justify a pre-failure positive window.

The unresolved `Maintenance on 30Apr at 12:00` source conflict remains metadata and creates no row label.

## Segment and leakage controls

Observation segments are rebuilt from ordered timestamps, with a new segment beginning when the gap exceeds 15 seconds. Pre-event exclusions and any future warning state may be assigned only inside the same segment as the corresponding event. No window may bridge one of the 363 verified temporal gaps.

Chronological train, validation, and test partitions remain unchanged. Rows in the two-hour partition buffers are excluded.

## Generated evidence

```text
data/processed/metropt3_target_states.parquet
outputs/metropt3_target_materialization_report.json
```

The Parquet output contains `timestamp`, `segment_id`, `partition`, `target_state`, `binary_target`, `source_event`, and `exclusion_reason`. The JSON report records checksums, row counts, state counts, partition counts, segment count, preserved conflict count, and scope controls.

## Reproducible command

```powershell
python -m predictive_maintenance.analysis.target_materialization `
  config\metropt3_target_definition.json `
  --parquet data\processed\metropt3_air_compressor.parquet `
  --output data\processed\metropt3_target_states.parquet `
  --report outputs\metropt3_target_materialization_report.json
```

The command rejects checksum mismatches, missing or duplicate timestamps, incorrect coverage, invalid policy, and failed DuckDB operations. Outputs use temporary `.part` files and atomic replacement.

## Component boundary

This component produces governed row states and evidence. It does not create a verified negative class, engineer predictive features, select a model, train a model, or report performance.

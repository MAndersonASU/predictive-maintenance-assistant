# Governed Row-Level Target-State Materialization

## Purpose

This method converts the four documented MetroPT-3 failure intervals into an
auditable row-state table. It preserves uncertainty instead of manufacturing a
binary classification dataset before trustworthy negative examples exist.

## State policy

Each timestamp receives exactly one state:

- `documented_failure`: the timestamp falls inside one of the four exact UCI
  failure intervals. `binary_target` is `1` only for this state.
- `excluded_pre_event`: the timestamp is within the two-hour buffer immediately
  before an event and remains in the event's observation segment.
- `excluded_partition_buffer`: the timestamp falls between the governed train,
  validation, and test partitions.
- `unverified`: the timestamp has no documented failure or exclusion evidence.
  It is not interpreted as healthy and receives a null binary target.
- `warning_not_enabled`: reserved in the schema but never assigned. The warning
  horizon is explicitly `null` because the current evidence does not justify a
  pre-failure positive window.

The unresolved `Maintenance on 30Apr at 12:00` source conflict remains metadata.
It creates no timestamp interval and therefore no row label.

## Segment and leakage controls

The implementation rebuilds observation segments from ordered timestamps. A
new segment begins when the gap exceeds 15 seconds. Pre-event exclusions and
any future warning state may be assigned only inside the same segment as the
corresponding event. No window is allowed to bridge one of the 363 verified
temporal gaps.

The existing chronological train, validation, and test partitions remain
unchanged. Rows in the two-hour partition buffers are excluded. No preprocessing
is fitted, no features are created, and no model is trained.

## Generated evidence

The command writes two ignored artifacts:

```text
data/processed/metropt3_target_states.parquet
outputs/metropt3_target_materialization_report.json
```

The Parquet output contains only `timestamp`, `segment_id`, `partition`,
`target_state`, `binary_target`, `source_event`, and `exclusion_reason`. The JSON
report records input and output checksums, row counts, state counts, partition
counts, segment count, preserved conflict count, and scope controls.

## Reproducible command

From the repository root with `.venv` active:

```powershell
python -m predictive_maintenance.analysis.target_materialization `
  config\metropt3_target_definition.json `
  --parquet data\processed\metropt3_air_compressor.parquet `
  --output data\processed\metropt3_target_states.parquet `
  --report outputs\metropt3_target_materialization_report.json
```

The command rejects a checksum mismatch, missing or duplicate timestamps,
incorrect timestamp coverage, an invalid policy, or a failed DuckDB operation.
Both outputs use temporary `.part` files and atomic replacement.

## Current boundary

This milestone produces governed row states and evidence only. It does not
create a verified negative class, engineer predictive features, select a model,
train a model, or report performance.

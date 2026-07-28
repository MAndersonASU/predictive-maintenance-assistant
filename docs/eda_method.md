# Reproducible Exploratory Data Analysis

## Purpose

This document defines the implemented exploratory-analysis method for the verified MetroPT-3 Parquet dataset. The analysis is descriptive and occurs before anomaly or failure-target definition, feature engineering, data splitting, or model training.

## Governed Input

The workflow reads the generated analytical dataset at:

```text
data/processed/metropt3_air_compressor.parquet
```

The source must expose the verified 17-column DuckDB analytical schema. DuckDB reads the preserved unnamed Parquet column as `C0`.

## Implemented Analysis

The workflow performs the following reproducible steps:

1. Validates that the Parquet input exists, is a file, and is non-empty.
2. Opens an in-memory DuckDB connection and creates a temporary analytical view over the Parquet file.
3. Validates the complete expected analytical schema.
4. Measures row count, first and last timestamps, elapsed time, and observed calendar days.
5. Calculates minimum, 1st percentile, 25th percentile, median, mean, 75th percentile, 99th percentile, maximum, and population standard deviation for seven continuous signals.
6. Calculates zero/one row counts and percentages for eight governed binary operating signals.
7. Identifies temporal gaps exceeding the configured threshold.
8. Separates the dataset into observation segments so analysis does not assume continuity across temporal gaps.
9. Writes JSON, CSV, and SVG analytical artifacts through temporary `.part` files and atomic replacement.
10. Records the input path, size, SHA-256 checksum, configuration, schema, output locations, software versions, and explicit scope limitations.

## Default Configuration

| Setting | Default |
| --- | ---: |
| Gap threshold | 15.0 seconds |
| Largest gap details retained | 20 |
| DuckDB database | In-memory |
| Output directory | `outputs/eda/` |

The 15-second threshold preserves the previously verified data-quality rule: the dominant interval is 10 seconds, and intervals greater than 15 seconds are treated as temporal gaps.

## Generated Outputs

```text
outputs/eda/metropt3_eda_summary.json
outputs/eda/signal_summary.csv
outputs/eda/operating_state_frequencies.csv
outputs/eda/temporal_segments.csv
outputs/eda/temporal_gaps.csv
outputs/eda/figures/operating_state_frequencies.svg
outputs/eda/figures/signal_distribution_overview.svg
```

These generated artifacts remain excluded from Git by the repository's existing `outputs/*` rule. Only source code, tests, and professional documentation are committed.

## Interpretation Boundaries

The workflow does not:

- define normal or abnormal sensor limits;
- label failures or anomalies;
- claim causal relationships between signals;
- create model features;
- create train, validation, or test partitions;
- train or evaluate a predictive model.

Observed distributions and operating-state frequencies are descriptive evidence. Engineering interpretation requires traceable dataset documentation and later target-definition work.

## Command-Line Execution

```powershell
python .\src\predictive_maintenance\analysis\eda.py
```

To replace a previously reviewed output set:

```powershell
python .\src\predictive_maintenance\analysis\eda.py --overwrite
```

The overwrite option is explicit because existing analytical artifacts are protected from silent replacement.

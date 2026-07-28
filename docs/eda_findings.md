# MetroPT-3 Exploratory Data Analysis Findings

## Purpose

This document records verified descriptive findings from the reproducible exploratory data analysis of the governed MetroPT-3 Parquet dataset.

The analysis is intentionally limited to data description. It does not define anomalies, failures, operating limits, prediction targets, model features, or causal relationships.

## Governed Input

The analysis used:

```text
data/processed/metropt3_air_compressor.parquet
```

Verified input identity:

```text
SHA-256: 50f9c0640bde18069270e639d451e79fa1243e917d4ef0e45ac99dc4bf7c80a3
Rows: 1,516,948
Columns: 17
```

The input was queried directly with an in-memory DuckDB connection.

## Timestamp Coverage

| Measurement | Verified value |
| --- | ---: |
| First timestamp | `2020-02-01T00:00:00` |
| Last timestamp | `2020-09-01T03:59:50` |
| Observed calendar days | 212 |
| Gap threshold | 15.0 seconds |
| Temporal gaps | 363 |
| Observation segments | 364 |
| Largest retained gap | 172,918 seconds |
| Largest retained gap | Approximately 48.03 hours |

The dataset cannot be treated as one uninterrupted time series. Analysis that depends on temporal adjacency must respect the 364 verified observation segments.

## Continuous-Signal Findings

Seven continuous signals were summarized with minimum, 1st percentile, 25th percentile, median, mean, 75th percentile, 99th percentile, maximum, and population standard deviation.

Selected verified observations:

- `TP2` has a median near `-0.012`, while its mean is approximately `1.368`. Its upper tail extends above `10`, showing a strongly uneven distribution.
- `DV_pressure` has a median near `-0.020` and a mean near `0.056`, while its maximum reaches `9.844`. Most observations are concentrated close to the lower end of the recorded range.
- `TP3` and `Reservoirs` have similar central values, with medians of `8.96`.
- `H1` has a median of `8.784`, while its minimum is slightly below zero.
- `Oil_temperature` has a median of `62.7`, a 1st percentile of `48.825`, a 99th percentile of `76.175`, and a maximum of `89.05`.
- `Motor_current` has a median near `0.045`, a mean near `2.050`, a 75th percentile near `3.808`, and a maximum of `9.295`.

These measurements describe observed distributions only. They do not establish normal ranges or abnormal thresholds.

## Operating-State Frequencies

Eight governed binary signals were summarized for states `0` and `1`.

Verified state-1 frequencies:

| Signal | State-1 percentage |
| --- | ---: |
| `COMP` | 83.70% |
| `DV_eletric` | 16.06% |
| `Towers` | 91.98% |
| `MPG` | 83.27% |
| `LPS` | 0.34% |
| `Pressure_switch` | 99.14% |
| `Oil_level` | 90.42% |
| `Caudal_impulses` | 93.71% |

`LPS=1` is uncommon in the recorded data, while `Pressure_switch=1` is present in nearly all rows. These frequencies are descriptive and are not failure labels.

## Temporal Segmentation Findings

The 363 verified gaps divide the dataset into 364 observation segments.

The largest continuous segment contains:

```text
36,599 rows
Start: 2020-03-24T04:03:08
End:   2020-03-28T08:49:39
Span:  approximately 100.78 hours
```

Several other segments span between approximately 50 and 72 hours. Segment size varies substantially, so later time-dependent analysis must avoid assuming equal or uninterrupted observation windows.

## Generated Evidence

The reproducible workflow generated the following ignored analytical artifacts:

```text
outputs/eda/metropt3_eda_summary.json
outputs/eda/signal_summary.csv
outputs/eda/operating_state_frequencies.csv
outputs/eda/temporal_segments.csv
outputs/eda/temporal_gaps.csv
outputs/eda/figures/operating_state_frequencies.svg
outputs/eda/figures/signal_distribution_overview.svg
```

The workflow retained the 20 largest gap details in `temporal_gaps.csv` while recording the full verified gap count of 363 in the summary metadata.

Both SVG figures were visually reviewed. Titles, labels, values, and captions were readable and were not cut off.

## Reproducibility Evidence

- The complete repository test suite passed: 26 tests.
- The EDA-specific test suite passed: 7 tests.
- The workflow produced no remaining `.part` files.
- Generated artifacts remain excluded from Git under the existing `outputs/*` rule.
- The workflow recorded the input checksum, schema, configuration, software versions, and output locations.
- Existing outputs require explicit overwrite permission.

## Interpretation Limitations

The analysis does not:

- establish equipment-specific operating limits;
- define anomaly or failure events;
- determine whether rare states are abnormal;
- establish causal relationships between signals;
- account for maintenance labels or event documentation;
- create train, validation, or test partitions;
- engineer predictive features;
- train or evaluate a machine-learning model.

The next engineering work must define target meaning and temporal evaluation boundaries only after the descriptive evidence and source documentation are reviewed together.

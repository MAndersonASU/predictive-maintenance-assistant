# Engineering Log

## Project

**Intelligent Predictive Maintenance and Technical Knowledge Assistant**

Repository: `MAndersonASU/predictive-maintenance-assistant`

## Purpose

This log records only implemented and verified engineering work. Planned capabilities remain explicitly identified as future work until they are developed, tested, committed, and synchronized with the public repository.

## Current Verified State

- Active branch: `main`
- Remote tracking branch: `origin/main`
- Public repository: verified
- Latest verified Day 8 implementation commit: `4ab2333b2684447e62fa45fc6e0fe0aaf989b863`
- Commit message: `Document MetroPT-3 failure-event provenance`
- Local and remote commit identity at the end of the Day 8 implementation: matched at `4ab2333`
- Working tree at the end of the Day 8 implementation: clean
- Complete repository test suite: 42 passing tests
- Generated datasets, reports, figures, and temporary files: excluded from Git under governed ignore rules

## Implemented Milestones

### Repository Foundation and Protection

- Initialized the Git repository and established `main` as the default branch.
- Connected the repository to GitHub through `origin`.
- Created the professional project structure and README.
- Excluded virtual environments, credentials, environment files, private keys, caches, logs, local databases, model artifacts, raw data, processed data, and generated outputs.
- Verified representative ignore behavior and public-repository safety controls.

### Source Governance

- Created `data/source_manifest.csv` and registered the MetroPT-3 dataset.
- Recorded source URL, DOI, licensing, expected filename, access information, checksum fields, and processing status.
- Created `docs/document_manifest.csv` for governed technical references.
- Preserved the distinction between exact dataset documentation and authoritative general domain references.

### Governed Data Acquisition

Implemented deterministic acquisition in `src/predictive_maintenance/data/acquire.py` with:

- project-relative paths;
- streaming download through `.part` files;
- ZIP integrity and archive-member validation;
- controlled extraction without silent overwrite;
- exact 17-column source-header validation;
- SHA-256 calculation and atomic manifest updates;
- immutable storage of governed source files under ignored `data/raw/`.

Verified source checksums:

- Archive: `aab991a970e58210de853bb8078ce0e63abb4d9412fdc5c79792dae3d8e1721a`
- CSV: `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`
- Dataset PDF: `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`

### Data-Quality Profiling

Implemented deterministic, read-only profiling in `src/predictive_maintenance/data/data_quality.py` with controlled tests in `tests/test_data_quality.py`.

Verified results:

- 1,516,948 rows and 17 columns
- Zero row-width mismatches
- Zero exact duplicate rows
- Zero missing values
- Zero timestamp parse failures
- Zero out-of-order or adjacent duplicate timestamps
- Zero numeric-coercion failures
- Zero non-finite numeric values
- Zero invalid supported binary values
- Dominant sampling interval: 10 seconds
- Intervals above the 15-second gap threshold: 363
- Largest gap: 172,918 seconds, approximately 48.033 hours
- Raw source modification: none
- Controlled data-quality tests: 12 passing

The temporal gaps are a governed limitation. Later time-dependent calculations must not assume continuity across them.

### Reproducible Parquet Conversion and DuckDB Access

Implemented `src/predictive_maintenance/data/parquet_conversion.py` with:

- explicit governed Arrow schema;
- preservation of the unnamed source column;
- streaming CSV reading;
- Zstandard compression;
- Parquet statistics and schema validation;
- row-count and column-count verification;
- source-preservation checks before and after conversion;
- `.part` handling and cleanup after failure;
- atomic JSON metadata writing;
- direct in-memory DuckDB validation over the completed Parquet file.

Verified results:

- Source rows: 1,516,948
- Parquet rows: 1,516,948
- Columns: 17
- Source CSV size: 218,300,507 bytes
- Parquet size: 24,485,606 bytes
- Source CSV SHA-256: `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`
- Parquet SHA-256: `50f9c0640bde18069270e639d451e79fa1243e917d4ef0e45ac99dc4bf7c80a3`
- Compression: Zstandard
- PyArrow: `25.0.0`
- DuckDB: `1.5.5`
- Permanent database created: no
- Controlled Parquet and DuckDB tests: 7 passing

Generated artifacts remain ignored:

```text
data/processed/metropt3_air_compressor.parquet
outputs/metropt3_parquet_metadata.json
```

### Reproducible Gap-Aware Exploratory Analysis

Implemented `src/predictive_maintenance/analysis/eda.py` and supporting documentation and tests.

Verified results:

- Input rows: 1,516,948
- Input columns: 17
- Input Parquet SHA-256: `50f9c0640bde18069270e639d451e79fa1243e917d4ef0e45ac99dc4bf7c80a3`
- Timestamp coverage: `2020-02-01 00:00:00` through `2020-09-01 03:59:50`
- Observed calendar days: 212
- Temporal gaps above 15 seconds: 363
- Gap-aware observation segments: 364
- Largest temporal gap: 172,918 seconds
- Continuous-signal summaries: 7
- Binary operating-state frequency records: 16
- Segment records: 364
- Largest-gap details retained: 20
- SVG figures generated and visually reviewed: 2
- Remaining `.part` files after success: 0
- Controlled EDA tests: 7 passing

Generated outputs remain under ignored `outputs/eda/`. The EDA is descriptive only and did not create failure labels, predictive features, models, or performance claims.

### Governed Target Definition and Temporal Evaluation

Implemented `src/predictive_maintenance/analysis/target_definition.py`, `config/metropt3_target_definition.json`, `tests/test_target_definition.py`, and `docs/target_definition_method.md`.

The validator enforces:

- governed dataset identity and timestamp coverage;
- complete event provenance and exact dataset matching for documented events;
- valid access dates and persistent source identifiers;
- unique, ordered, non-overlapping event intervals;
- optional prediction windows that precede observed events and satisfy minimum warning time;
- chronological train, validation, and test partitions with temporal buffers;
- required leakage controls;
- the policy that unlabeled rows are not automatically assumed healthy;
- atomic validation-report writing and actionable errors.

Day 7 established the governed validation framework without creating row-level labels. Verified Day 7 implementation commit: `607bac4` (`Implement governed target definition and temporal evaluation`). The Day 7 checkpoint documentation commit was `d9fc5b9`.

### Exact MetroPT-3 Failure-Event Provenance

Day 8 replaced the ambiguous design placeholder with four intervals documented by the exact 2020 MetroPT-3 UCI dataset source.

Governed source identity:

- Dataset: MetroPT-3 Dataset
- Publisher: UCI Machine Learning Repository
- DOI: `10.24432/C5VW3R`
- Local analytical coverage: `2020-02-01 00:00:00` through `2020-09-01 03:59:50`
- Source section: Additional Information - Failure Information
- Access date recorded in configuration: July 30, 2026

Documented intervals:

| Event ID | Start | End | Interpretation |
|---|---|---|---|
| `uci_air_leak_2020_04_18` | `2020-04-18 00:00` | `2020-04-18 23:59` | High-stress air-leak event metadata |
| `uci_air_leak_2020_05_29` | `2020-05-29 23:30` | `2020-05-30 06:00` | High-stress air-leak event metadata |
| `uci_air_leak_2020_06_05` | `2020-06-05 10:00` | `2020-06-07 14:30` | High-stress air-leak event metadata |
| `uci_air_leak_2020_07_15` | `2020-07-15 14:30` | `2020-07-15 19:00` | High-stress air-leak event metadata |

The May 29-30 source entry also says `Maintenance on 30Apr at 12:00`. This conflicts with the event dates. The project preserves the statement as one unresolved provenance conflict and does not silently correct, reinterpret, or use it to change the documented event interval.

Day 8 implementation changes:

- Upgraded the governed specification to schema version 2.
- Added exact dataset source identifiers, access dates, dataset-match controls, and source-conflict records.
- Added `docs/failure_event_provenance.md`.
- Updated the method documentation to distinguish the 2020 UCI failure records from later MetroPT research data.
- Removed the invented prediction-window placeholder; prediction-window count is now zero.
- Preserved the four records as event metadata rather than row-level labels.
- Strengthened target-definition tests from 9 to 16.

Verified Day 8 validation report:

- Status: `valid`
- Schema version: 2
- Event count: 4
- Documented events: 4
- Derived events: 0
- Ambiguous events: 0
- Prediction windows: 0
- Provenance conflicts: 1
- Minimum warning interval: 2.0 hours
- Evaluation partition buffer: 2.0 hours
- Row-level labels created: no
- Predictive features engineered: no
- Models trained: no
- Performance metrics reported: no
- Remaining `.part` files: 0

Verified Day 8 testing:

- Python syntax compilation: passed
- Focused target-definition tests: 16 passing
- Complete repository test suite: 42 passing
  - 12 data-quality tests
  - 7 Parquet and DuckDB tests
  - 7 exploratory-analysis tests
  - 16 target-definition tests
- Failures: 0
- Errors: 0

Verified Day 8 implementation commit and push:

- Commit: `4ab2333b2684447e62fa45fc6e0fe0aaf989b863`
- Message: `Document MetroPT-3 failure-event provenance`
- Scope: 5 files changed, 330 insertions, 73 deletions
- New file: `docs/failure_event_provenance.md`
- Push: `origin/main` advanced from `d9fc5b9` to `4ab2333`
- End-of-implementation synchronization: local `HEAD` and `origin/main` matched
- End-of-implementation working tree: clean

## Verified Repository Artifacts

Source modules:

```text
src/predictive_maintenance/data/acquire.py
src/predictive_maintenance/data/data_quality.py
src/predictive_maintenance/data/parquet_conversion.py
src/predictive_maintenance/analysis/eda.py
src/predictive_maintenance/analysis/target_definition.py
```

Controlled test modules:

```text
tests/test_data_quality.py
tests/test_parquet_conversion.py
tests/test_eda.py
tests/test_target_definition.py
```

Professional documentation and governed configuration:

```text
ENGINEERING_LOG.md
config/metropt3_target_definition.json
docs/eda_method.md
docs/eda_findings.md
docs/target_definition_method.md
docs/failure_event_provenance.md
```

## Architecture Decisions

### Immutable and Traceable Inputs

Original governed source files remain immutable under ignored raw storage. Derived analytical artifacts never replace source data. Every source-dependent claim must preserve source identity and provenance.

### Columnar Local Analytics

Parquet is the governed analytical format and DuckDB provides direct in-memory SQL access. This supports typed, compressed, column-selective analysis without requiring a permanent local database.

### Gap-Aware Time-Series Processing

The dataset contains 364 verified observation segments separated by 363 temporal gaps greater than 15 seconds. Rolling windows, lags, labels, features, and evaluation relationships must not cross these segment boundaries.

### Evidence Before Labels

Exploratory rarity, sensor patterns, and operating-state frequencies are not automatic anomaly or failure labels. The exact dataset source now supplies four documented event intervals, but these are still event metadata until a separate governed materialization policy defines row-level targets.

### Leakage-Safe Evaluation

Evaluation remains strictly chronological. Training precedes validation, validation precedes testing, and temporal buffers separate partitions. Fitted preprocessing and selection steps must use training data only.

### Conflict Preservation

Source conflicts are retained explicitly. They are not silently resolved through guesswork. The unresolved `30Apr` note remains recorded but does not alter the four documented event intervals.

### Public Repository Policy

The repository contains source code, tests, schemas, configuration, manifests, documentation, and reproducible setup information. It excludes credentials, private files, large data, generated outputs, local databases, and unverified performance claims.

### Engineering Log Maintenance

`ENGINEERING_LOG.md` must be updated for each completed engineering milestone with verified files, validations, evidence, architecture decisions, commit and push state, repository state, and one exact next milestone.

## Current Engineering Workstream

Exact failure-event provenance confirmation is complete. The four documented UCI intervals are governed, the unresolved source conflict is preserved, and the validation framework rejects unsupported assumptions.

The active workstream is now the design of a governed row-level target-materialization policy. This work must define how documented event intervals, optional pre-event warning horizons, excluded ambiguous periods, chronological partitions, and the 364 observation segments translate into auditable row-level target states without crossing temporal gaps or treating every unlabeled row as verified healthy operation.

## Next Engineering Milestone

Define and validate the row-level target-materialization policy for the four documented MetroPT-3 failure intervals.

The milestone must:

- define explicit target states and exclusion states;
- define any warning horizon before implementation rather than inventing one inside code;
- keep all labels and windows inside individual verified observation segments;
- preserve chronological partitions and leakage controls;
- preserve the unresolved source conflict without converting it into a label;
- generate auditable label counts and metadata;
- stop before predictive feature engineering, model training, or performance reporting.

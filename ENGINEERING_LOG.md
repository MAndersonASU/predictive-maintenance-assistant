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
- Latest verified implementation commit: `2dcf55a37bbbe523271bc8aff91379f6bc67869e`
- Commit message: `Implement robust-distance validation baseline`
- Local and remote implementation commit identity: matched at `2dcf55a37bbbe523271bc8aff91379f6bc67869e`
- Working tree after the implementation push and before this engineering-log update: clean
- Complete repository test suite: 86 passing tests
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

### Governed Row-Level Target Materialization

Day 9 implemented the audited translation from governed event metadata to row-level target states without inventing a negative class or crossing observation gaps.

Implemented artifacts:

- `src/predictive_maintenance/analysis/target_materialization.py`
- `tests/test_target_materialization.py`
- `docs/target_materialization_method.md`
- updated `config/metropt3_target_definition.json`

The materialization policy enforces:

- seven governed output columns: `timestamp`, `segment_id`, `partition`, `target_state`, `binary_target`, `source_event`, and `exclusion_reason`;
- four documented UCI failure intervals and one preserved provenance conflict;
- 364 gap-aware observation segments;
- chronological train, validation, test, and excluded partitions;
- a 2.0-hour pre-event exclusion period;
- no assignments across segment boundaries;
- no automatic conversion of unverified rows into a negative class;
- atomic JSON and Parquet output handling with cleanup of partial files.

Verified production evidence:

- Status: `valid`
- Input rows: 1,516,948
- Output rows: 1,516,948
- Observation segments: 364
- Documented events: 4
- Preserved provenance conflicts: 1
- Cross-segment assignments: 0
- Documented-failure rows: 29,954
- Excluded partition-buffer rows: 1,453
- Excluded pre-event rows: 2,776
- Unverified rows: 1,482,765
- Warning horizon: disabled
- Verified negative class created: no
- Predictive features engineered: no
- Models trained: no
- Performance metrics reported: no
- Remaining `.part` files: 0
- Output Parquet SHA-256: `6a88ef1333664ceb477632c7a80cb6b3985f850254e3e93211f57681da9e5bd0`
- Output Parquet size: 5,303,389 bytes
- Validation-report size: 2,635 bytes

Verified testing:

- Target-definition and target-materialization tests: 27 passing
- Complete repository test suite: 53 passing
- Failures: 0
- Errors: 0

Verified Day 9 implementation commit and push:

- Commit: `c16a9465fed7755d1b3a86ab84f489b83d6a886f`
- Message: `Materialize governed MetroPT-3 target states`
- Scope: 4 files changed, 994 insertions, 4 deletions
- Push: `origin/main` advanced from `a7a8bb7` to `c16a946`
- Local `HEAD` and `origin/main` matched after fetch verification
- End-of-implementation working tree: clean


### Leakage-Safe MetroPT-3 Feature Engineering

Day 10 implemented the reproducible feature layer over the governed sensor history and row-level target states.

Implemented artifacts:

- `config/metropt3_feature_engineering.json`
- `src/predictive_maintenance/analysis/feature_engineering.py`
- `tests/test_feature_engineering.py`
- `docs/feature_engineering_method.md`

The feature contract and implementation enforce:

- preservation of seven continuous and eight operating-state current values;
- causal one-row lag and difference features for each continuous signal;
- causal 6-row and 30-row population means and standard deviations;
- history resets at every observation-segment or chronological-partition change;
- explicit partial-history evidence through `history_rows_available`, `has_lag_1_history`, `has_full_6_row_history`, and `has_full_30_row_history`;
- preservation of target state, binary target, source event, exclusion reason, partition, and segment governance;
- checksum, schema, row-count, and timestamp-set validation before output acceptance;
- atomic Parquet and JSON evidence writing.

Verified production evidence:

- Input rows: 1,516,948
- Output rows: 1,516,948
- Output columns: 69
- Feature contract SHA-256: `7f92fbb63806ae1a9c529d37d0f8b101cc992cf7194e28ea26c9e21a7f171242`
- Feature Parquet SHA-256: `a06e64a6e183a5c3a5166f997da8c51523d9db33b907a1adf5d824abca567d93`
- Verified negative class created: no
- Learned preprocessing fitted: no
- Models trained: no
- Performance metrics reported: no

Verified testing and repository state:

- Focused feature-engineering tests: 10 passing
- Complete repository test suite: 63 passing
- Failures: 0
- Errors: 0
- Generated feature Parquet and evidence report: excluded from Git
- Commit: `a8ddc93717c33c134e1ef6c8c3de32ef90fd33a7`
- Message: `Implement leakage-safe MetroPT-3 feature engineering`
- Scope: 4 files changed
- Local `HEAD` and `origin/main` matched after push
- End-of-implementation working tree: clean

Generated artifacts remain ignored:

```text
data/processed/metropt3_features.parquet
outputs/metropt3_feature_engineering_report.json
```

### Governed Baseline-Evaluation Contract

Day 11 defined and validated the population, chronology, leakage controls, future transparent baseline, permitted metrics, and prohibited claims before any baseline fitting or performance reporting.

Implemented artifacts:

- `config/metropt3_baseline_evaluation.json`
- `src/predictive_maintenance/analysis/baseline_evaluation.py`
- `tests/test_baseline_evaluation.py`
- `docs/baseline_evaluation_method.md`

The contract and validator enforce:

- chronological train, validation, test, and excluded partitions;
- segment-safe complete 30-row feature history for eligible populations;
- eligible reference fitting from training-partition unlabeled rows only;
- exclusion of the training event from known-event evaluation;
- preservation of documented positives, exclusions, and unlabeled uncertainty;
- prohibition of an invented healthy-negative class;
- training-only fitting for any future learned preprocessing;
- a planned transparent robust-distance baseline with frozen training-derived parameters and threshold;
- operationally supportable metrics and explicit prohibition of unsupported accuracy, precision, specificity, and false-positive claims;
- checksum, schema, row-count, target-consistency, population, and chronology validation;
- atomic eligibility-Parquet and JSON evidence writing.

Verified production evidence:

- Status: `valid`
- Input rows: 1,516,948
- Output rows: 1,516,948
- Chronological-only evaluation: true
- Segment-safe history required: true
- Eligible reference-fit rows: 734,015
- Eligible scoring rows: 1,502,134
- Eligible validation/test alarm-burden rows: 738,281
- Eligible known-event evaluation rows: 21,210
- Documented-positive role rows: 29,838
- Excluded role rows: 14,814
- Unlabeled-reference role rows: 734,015
- Unlabeled-scoring role rows: 738,281
- Train partition rows: 748,228
- Validation partition rows: 333,107
- Test partition rows: 434,160
- Excluded partition rows: 1,453
- Unverified rows treated as negative: false
- Learned preprocessing fitted: no
- Model fitted: no
- Scores generated: no
- Alarms generated: no
- Performance metrics reported: no
- Eligibility Parquet SHA-256: `b34942fd35474f1688df8ac7db85d975dc10bf2ec23a72266d547bd6dd102e8d`

Verified testing and repository state:

- Focused baseline-evaluation tests: 11 passing
- Complete repository test suite: 74 passing
- Failures: 0
- Errors: 0
- Generated eligibility Parquet and contract report: excluded from Git
- Commit: `1d6a9b33d61e706ebf939d1efc6282d8777bcef8`
- Message: `Define governed baseline evaluation contract`
- Scope: 4 files changed, 774 insertions
- Push: `origin/main` advanced from `a8ddc93` to `1d6a9b3`
- Local `HEAD` and `origin/main` matched at the full commit identity after push
- End-of-implementation working tree: clean

Generated artifacts remain ignored:

```text
data/processed/metropt3_baseline_eligibility.parquet
outputs/metropt3_baseline_evaluation_contract_report.json
```

## Verified Repository Artifacts

Source modules:

```text
src/predictive_maintenance/data/acquire.py
src/predictive_maintenance/data/data_quality.py
src/predictive_maintenance/data/parquet_conversion.py
src/predictive_maintenance/analysis/eda.py
src/predictive_maintenance/analysis/target_definition.py
src/predictive_maintenance/analysis/target_materialization.py
src/predictive_maintenance/analysis/feature_engineering.py
src/predictive_maintenance/analysis/baseline_evaluation.py
```

Controlled test modules:

```text
tests/test_data_quality.py
tests/test_parquet_conversion.py
tests/test_eda.py
tests/test_target_definition.py
tests/test_target_materialization.py
tests/test_feature_engineering.py
tests/test_baseline_evaluation.py
```

Professional documentation and governed configuration:

```text
ENGINEERING_LOG.md
config/metropt3_target_definition.json
config/metropt3_feature_engineering.json
config/metropt3_baseline_evaluation.json
docs/eda_method.md
docs/eda_findings.md
docs/target_definition_method.md
docs/failure_event_provenance.md
docs/target_materialization_method.md
docs/feature_engineering_method.md
docs/baseline_evaluation_method.md
```

## Architecture Decisions

### Immutable and Traceable Inputs

Original governed source files remain immutable under ignored raw storage. Derived analytical artifacts never replace source data. Every source-dependent claim must preserve source identity and provenance.

### Columnar Local Analytics

Parquet is the governed analytical format and DuckDB provides direct in-memory SQL access. This supports typed, compressed, column-selective analysis without requiring a permanent local database.

### Gap-Aware Time-Series Processing

The dataset contains 364 verified observation segments separated by 363 temporal gaps greater than 15 seconds. Rolling windows, lags, labels, features, and evaluation relationships must not cross these segment boundaries.

### Evidence Before Labels

Exploratory rarity, sensor patterns, and operating-state frequencies are not automatic anomaly or failure labels. The four exact documented intervals have now been materialized as auditable row-level failure states, while all other observations remain explicitly unverified rather than being treated as healthy negatives.

### Leakage-Safe Evaluation

Evaluation remains strictly chronological. Training precedes validation, validation precedes testing, and temporal buffers separate partitions. Fitted preprocessing and selection steps must use eligible training-reference data only and then remain frozen for later partitions.

### Governed Baseline Interpretation

The selected future baseline is a transparent robust-distance method. Its reference population is an unlabeled training-period operating mixture, not a verified healthy class. Its score will represent unusualness relative to that reference and must not be described as a failure probability. Only operational metrics supported by the available positive and unlabeled evidence may be reported.

### Conflict Preservation

Source conflicts are retained explicitly. They are not silently resolved through guesswork. The unresolved `30Apr` note remains recorded but does not alter the four documented event intervals.

### Public Repository Policy

The repository contains source code, tests, schemas, configuration, manifests, documentation, and reproducible setup information. It excludes credentials, private files, large data, generated outputs, local databases, and unverified performance claims.

### Engineering Log Maintenance

`ENGINEERING_LOG.md` must be updated for each completed engineering milestone with verified files, validations, evidence, architecture decisions, commit and push state, repository state, and one exact next milestone.

## Current Engineering Workstream

Leakage-safe feature engineering and the governed baseline-evaluation contract are complete. The eligible populations, chronology, segment-safe history requirement, future transparent baseline, supported operational metrics, and prohibited claims are now explicit and validated. No learned preprocessing, model, score, alarm, or performance result has yet been produced.

The active workstream is now implementation of the transparent training-reference robust-distance baseline under the frozen Day 11 contract.

## Next Engineering Milestone

Implement and validate the transparent robust-distance baseline for validation-stage analysis while keeping the test partition locked.

The milestone must:

- select numeric model features only through the governed contract;
- fit medians and interquartile ranges on the 734,015 eligible training-reference rows only;
- record and exclude zero-IQR features with explicit reasons;
- apply the frozen training-derived parameters unchanged to eligible validation rows;
- calculate the maximum absolute robust z-score as unusualness, not failure probability;
- derive and freeze the candidate alarm threshold from eligible training-reference scores before validation analysis;
- report only supported validation-stage operational evidence, including known-event coverage, alarm latency, score stability, and alarm burden;
- preserve unlabeled uncertainty and avoid accuracy, precision, specificity, false-positive-rate, or healthy-class claims;
- keep the test partition locked until the complete baseline method and validation decisions are frozen;
- generate auditable model parameters, checksums, row counts, schema, and reproducibility evidence before any advanced-model comparison.

## Robust-Distance Validation Baseline

Status: Implemented and verified on August 2, 2026.

### Implemented Scope

Implemented a governed robust-distance baseline under the frozen baseline-evaluation contract.

Created and validated:

```text
config/metropt3_robust_distance.json
docs/robust_distance_method.md
src/predictive_maintenance/analysis/robust_distance.py
tests/test_robust_distance.py
```

The implementation:

- selects numeric model features through the governed contract;
- fits medians and interquartile ranges only on eligible training-reference rows;
- records and excludes features with zero training-reference IQR;
- defines unusualness as the maximum absolute robust z-score;
- derives and freezes the alarm threshold from training-reference scores;
- applies the frozen parameters unchanged to validation rows;
- keeps the test partition locked;
- preserves the uncertainty of unlabeled observations;
- reports alarm burden without describing it as a false-positive rate.

### Verification Evidence

Focused robust-distance test suite:

```text
Command: python -m unittest tests.test_robust_distance -v
Tests run: 12
Failures: 0
Errors: 0
```

Complete repository regression suite:

```text
Command: python -m unittest discover -s tests -v
Tests run: 86
Failures: 0
Errors: 0
Elapsed time: 2.765 seconds
```

Production execution:

```text
Eligible training-reference rows: 734,015
Validation rows scored: 329,624
Test rows scored: 0
Processing status: robust_distance_validation_completed
```

Frozen fitted parameters:

```text
Fit partition: train
Retained features: 48
Excluded zero-IQR features: 9
Threshold quantile: 0.995
Frozen threshold: 7857.013759410036
Test partition used: false
Parameter status: frozen_before_validation
```

Validation-stage evidence:

```text
Validation alarm burden: 0.00886109023344634
Validation alarm burden percentage: approximately 0.8861%
Alarms per 24 observed hours: approximately 76.56
Documented validation events: 2
Documented events covered: 1
Documented-event coverage fraction: 0.5
Covered event: uci_air_leak_2020_05_29
First-alarm latency for covered event: 23,228 seconds
Uncovered event: uci_air_leak_2020_06_05
```

The covered-event alarm occurred approximately 6 hours and 27 minutes after the documented interval began. These results establish reproducible baseline evidence but do not establish strong predictive performance.

### Governed Generated Artifacts

The following generated artifacts were verified as non-empty and remain excluded from Git:

```text
outputs/metropt3_robust_distance_parameters.json
data/processed/metropt3_validation_robust_distance.parquet
outputs/metropt3_robust_distance_validation_report.json
```

Verified file sizes:

```text
metropt3_robust_distance_parameters.json: 7,084 bytes
metropt3_validation_robust_distance.parquet: 2,322,058 bytes
metropt3_robust_distance_validation_report.json: 3,030 bytes
```

The generated evidence records source and contract checksums, fitted parameters, output checksums, row counts, software versions, governance controls, score summaries, alarm burden, documented-event coverage, and first-alarm latency.

### Repository Evidence

Implementation commit:

```text
Commit: 2dcf55a37bbbe523271bc8aff91379f6bc67869e
Message: Implement robust-distance validation baseline
Scope: 4 files changed, 639 insertions
Push: origin/main advanced from 7b03292 to 2dcf55a
```

Local `HEAD` and `origin/main` matched at the full commit identity after the push.

Verified repository state before this engineering-log update:

```text
Branch: main
Tracking branch: origin/main
Ahead/behind: none
Working tree: clean
```

### Engineering Interpretation

The baseline detected one of the two documented validation events, missed the other, and generated approximately 76.56 alarms per 24 observed hours. The baseline therefore requires governed validation diagnosis before test evaluation or comparison with a more advanced model.

Several retained features have very small but nonzero training-reference IQRs. These values can produce disproportionately large standardized contributions and require explicit diagnostic analysis. Their presence is not, by itself, evidence of an implementation error.

Alarm burden is not a false-positive rate because unlabeled operational observations are not verified healthy examples. Accuracy, precision, specificity, false-positive rate, ROC-AUC, and verified-healthy claims remain unsupported.

### Current Engineering Workstream

The transparent training-reference robust-distance baseline is implemented, tested, reproducible, and evaluated on the validation partition. Its fitted parameters and training-derived threshold are frozen. The test partition remains locked.

The active workstream is governed validation-stage baseline diagnosis and final baseline-decision freezing.

### Next Engineering Milestone

Perform and validate a governed diagnostic analysis of the frozen robust-distance baseline using training-reference and validation evidence only while keeping the test partition locked.

The analysis must:

- identify the retained features that dominate extreme scores and alarm rows;
- quantify the influence of very small nonzero IQRs;
- analyze alarm concentration by observation segment, operating state, and time;
- preserve the distinction between documented-event alarms and alarms on unlabeled rows;
- investigate the missed June 5 event and delayed May 29 detection;
- compare only a bounded set of training-derived threshold candidates;
- document proposed feature or threshold revisions with explicit evidence;
- freeze the complete baseline decision before opening the test partition;
- continue prohibiting unsupported classification and verified-healthy claims;
- generate auditable configuration, reports, checksums, tests, and reproducibility evidence.


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
- Latest verified implementation commit: `26f0024481f59dec65d1c0cd502d2b8e9d249762`
- Commit message: `Define governed advanced-model comparison contract`
- Local and remote implementation commit identity: matched at `26f0024481f59dec65d1c0cd502d2b8e9d249762`
- Working tree after the implementation push and before this engineering-log update: clean
- Complete repository test suite: 151 passing tests
- Generated datasets, reports, figures, and temporary files: excluded from Git under governed ignore rules
## Implemented Milestones

### Repository Foundation and Protection

- Initialized the Git repository and established `main` as the default branch.
- Connected the repository to GitHub through `origin`.
- Created the professional project structure and README.
- Excluded virtual environments, credentials, environment files, private keys, caches, logs, local databases, model artifacts, raw data, processed data, andgenerated outputs.
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

Day 9 implemented the audited translation from governed event metadata to row-level target states without inventing a negative class or crossing observationgaps.

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
src/predictive_maintenance/analysis/robust_distance.py
src/predictive_maintenance/analysis/robust_distance_diagnosis.py
src/predictive_maintenance/analysis/robust_distance_test_evaluation.py
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
tests/test_robust_distance.py
tests/test_robust_distance_diagnosis.py
tests/test_robust_distance_test_evaluation.py
```

Professional documentation and governed configuration:

```text
ENGINEERING_LOG.md
config/metropt3_target_definition.json
config/metropt3_feature_engineering.json
config/metropt3_baseline_evaluation.json
config/metropt3_robust_distance.json
config/metropt3_robust_distance_diagnosis.json
config/metropt3_robust_distance_test_evaluation.json
docs/eda_method.md
docs/eda_findings.md
docs/target_definition_method.md
docs/failure_event_provenance.md
docs/target_materialization_method.md
docs/feature_engineering_method.md
docs/baseline_evaluation_method.md
docs/robust_distance_method.md
docs/robust_distance_diagnosis_method.md
docs/robust_distance_test_evaluation_method.md
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

`ENGINEERING_LOG.md` must be updated for each completed engineering milestone with verified files, validations, evidence, architecture decisions, commit andpush state, repository state, and one exact next milestone.

## Current Engineering Workstream

The governed advanced-model comparison contract is implemented and validated. It fixes one bounded `IsolationForest` family, a shared frozen 48-feature set, training-only fitting and threshold derivation, validation-only deterministic candidate selection, supported operational evidence, prohibited claims, and a complete advanced-model test lock.

No advanced model has been fitted, scored, selected, or evaluated on test data. The transparent robust-distance baseline remains a finalized reference, and its test evidence remains prohibited from advanced-model design or tuning.

## Next Engineering Milestone

Implement and validate the governed Isolation Forest training-and-validation candidate workflow under the frozen comparison contract while keeping the advanced-model test partition locked.

The milestone must:

- use only the eight predetermined Isolation Forest candidates;
- fit every candidate on eligible training-reference rows only;
- use the same frozen 48-feature set for every candidate;
- derive each candidate threshold from eligible training scores at the fixed 0.995 quantile;
- apply frozen candidate parameters and thresholds to validation rows only;
- calculate only supported operational validation evidence;
- apply the frozen lexicographic selection rule without test evidence;
- freeze the selected candidate, threshold, and validation decision before any separate test authorization;
- preserve unlabeled uncertainty and all prohibited-claim controls.

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

The generated evidence records source and contract checksums, fitted parameters, output checksums, row counts, software versions, governance controls, scoresummaries, alarm burden, documented-event coverage, and first-alarm latency.

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

## Frozen Robust-Distance Validation Diagnosis

Status: Implemented, tested, and synchronized on August 4, 2026.

### Implemented Scope

Created and validated:

```text
config/metropt3_robust_distance_diagnosis.json
docs/robust_distance_diagnosis_method.md
src/predictive_maintenance/analysis/robust_distance_diagnosis.py
tests/test_robust_distance_diagnosis.py
```

The diagnosis:

- uses eligible training-reference and validation evidence only;
- reuses the frozen Day 12 feature medians, IQRs, and baseline decision without refitting them;
- compares only the bounded training-derived threshold quantiles `0.990`, `0.995`, and `0.999`;
- identifies dominant robust-distance contributions and retained features with very small nonzero IQRs;
- analyzes alarm concentration by observation segment, UTC hour, and an explicit ordered eight-indicator operating state;
- preserves unlabeled-row uncertainty and does not interpret alarm burden as a false-positive rate;
- keeps the test partition locked and rejects test rows in the diagnostic population.

The ordered operating-state indicators are:

```text
COMP
DV_eletric
Towers
MPG
LPS
Pressure_switch
Oil_level
Caudal_impulses
```

### Verification Evidence

Focused diagnosis tests:

```text
Command: python -m pytest .\tests\test_robust_distance_diagnosis.py -v
Tests collected: 20
Tests passed: 20
Failures: 0
Errors: 0
Elapsed time: 0.23 seconds
```

Complete repository regression suite:

```text
Command: python -m pytest
Tests collected: 106
Tests passed: 106
Failures: 0
Errors: 0
Elapsed time: 3.07 seconds
```

Production diagnosis:

```text
Processing status: robust_distance_diagnosis_completed
Eligible training-reference rows: 734,015
Validation rows scored: 329,624
Test rows: 0
```

Operating-state totals reconcile to the validation population:

```text
Observed operating states: 12
Validation-scored rows: 329,624
Alarm rows: 2,747
Eligible unlabeled alarm-burden rows: 310,007
Test rows: 0
```

Selected state-level evidence:

- The dominant operating state contained 242,167 scored rows and 2,622 alarms. Its alarm-burden fraction was `0.010828088606967639`, approximately 1.083%, over 242,148 eligible unlabeled burden rows.
- A smaller state contained 251 scored and eligible unlabeled burden rows with 42 alarms. Its alarm-burden fraction was `0.16733067729083664`, approximately 16.73%.
- A three-row state contained one alarm and a burden fraction of `0.3333333333333333`. This is recorded as rare-state evidence and is not treated as a stable rate estimate.
- Alarm-burden fractions use eligible unlabeled burden rows as their denominator, not all scored rows.

These burdens are not false-positive rates because the operational rows are not verified healthy negatives.

### Governed Generated Artifact

The regenerated diagnostic report remains excluded from Git:

```text
outputs/metropt3_robust_distance_diagnostic_report.json
```

The report records input checksums, diagnostic populations, frozen-baseline evidence, dominant features, small-IQR evidence, alarm concentration by segment, UTC hour, and operating state, bounded training-derived threshold candidates, documented-event coverage and latency, the frozen baseline decision, and limitations.

### Repository Evidence

Implementation commit:

```text
Commit: f16c7ab8c750d7b16825f54f0e366d485be1dd65
Message: Diagnose robust-distance validation behavior
Scope: 4 files changed, 525 insertions
Push: origin/main advanced from 739baca to f16c7ab
```

Verified repository state before this engineering-log update:

```text
Branch: main
Tracking branch: origin/main
Local HEAD: f16c7ab8c750d7b16825f54f0e366d485be1dd65
Remote origin/main: f16c7ab8c750d7b16825f54f0e366d485be1dd65
Ahead/behind: none
Working tree: clean
```

### Engineering Interpretation

The diagnosis confirms that alarms are concentrated in particular operating states and that rare states can produce numerically large burden fractions from very small samples. State-level burden therefore requires its row count and eligible denominator for interpretation. The diagnostic evidence does not establish verified false positives, failure probability, accuracy, precision, specificity, or ROC AUC.

The baseline family remains `maximum_absolute_robust_z_score`, the configured selected threshold quantile remains `0.995`, and the test partition remains locked. The complete baseline decision is frozen after validation diagnosis.

## One-Time Frozen Robust-Distance Test Evaluation

Status: Implemented, tested, executed, committed, pushed, and synchronized on August 5, 2026.

### Implemented Scope

Created and validated:

```text
config/metropt3_robust_distance_test_evaluation.json
docs/robust_distance_test_evaluation_method.md
src/predictive_maintenance/analysis/robust_distance_test_evaluation.py
tests/test_robust_distance_test_evaluation.py
```

The evaluator:

- loads the previously frozen retained features, medians, IQR values, threshold quantile, and threshold;
- rejects parameter, threshold, validation-decision, or evidence-chain mismatches;
- performs no refitting and no threshold revision;
- scores only eligible rows in the locked `test` partition;
- writes zero training or validation rows to the test-score output;
- reports documented-event coverage, first-alarm latency, score evidence, and unlabeled alarm burden;
- preserves the interpretation that unverified operational rows are not verified healthy negatives;
- blocks unsupported classification, false-positive-rate, and failure-probability claims.

### Verification Evidence

Focused test suite:

```text
Command: python -m pytest tests/test_robust_distance_test_evaluation.py -q
Tests passed: 23
Failures: 0
Errors: 0
Elapsed time: 0.23 seconds
```

Complete repository regression suite:

```text
Command: python -m pytest -q
Tests passed: 129
Failures: 0
Errors: 0
Elapsed time: 4.36 seconds
```

Production execution:

```text
Processing status: robust_distance_test_evaluation_completed
Retained features: 48
Threshold quantile: 0.995
Frozen threshold: 7857.013759410036
Test rows scored: 429,867
Test alarm rows: 4,670
Training rows scored: 0
Validation rows scored: 0
```

Documented test-event evidence:

```text
Documented events: 1
Documented events covered: 1
Coverage fraction: 1.0
Event: uci_air_leak_2020_07_15
Event scored rows: 1,593
Alarm rows within the documented event: 1
First-alarm latency: 15,804 seconds
```

The first documented-event alarm occurred approximately 4 hours and 23 minutes after the scored event interval began. Coverage of one event does not establish general predictive performance.

Eligible unlabeled burden evidence:

```text
Eligible unlabeled burden rows: 428,274
Unlabeled alarm count: 4,669
Alarm-burden fraction: 0.010901899251413815
Alarm-burden percentage: approximately 1.0902%
Alarms per 24 observed hours: approximately 94.19
```

These alarms are operational burden observations, not verified false positives.

### Governed Generated Artifacts

The following generated artifacts were verified as non-empty and remain excluded from Git:

```text
data/processed/metropt3_test_robust_distance.parquet
outputs/metropt3_robust_distance_test_report.json
```

Verified file evidence:

```text
Test-score Parquet size: 3,199,394 bytes
Test-score Parquet SHA-256: 55512A95D274A91559520CA781A290D05E6D0B07E7C4C5198F4F33716AAF268A
Test report size: 3,288 bytes
Test report SHA-256: 0892615A7A7E291BD84AF8AA461999ED171447E108BE91E63EB8339629C29DB4
```

The test-score Parquet contains only the test partition:

```text
Partition: test
Scored rows: 429,867
Alarm rows: 4,670
```

### Repository Evidence

Implementation commit:

```text
Commit: e979eea9957d548f372c37c29141ca7d500b93fb
Message: Evaluate frozen robust-distance baseline on test data
Scope: 4 files changed, 1,013 insertions
Push: origin/main advanced from a913f37 to e979eea
```

Verified synchronized state after the implementation push:

```text
Branch: main
Tracking branch: origin/main
Local HEAD: e979eea9957d548f372c37c29141ca7d500b93fb
Remote origin/main: e979eea9957d548f372c37c29141ca7d500b93fb
Ahead/behind: none
Working tree: clean
```

### Engineering Interpretation

The frozen test evaluation provides final transparent-baseline evidence. The baseline covered the one documented test event but produced only one alarm within its 1,593 scored event rows, with a latency of 15,804 seconds.

The test alarm burden was higher than the validation alarm burden. This observation may be reported as evidence of changed operational burden, but it must not be used to retune the finalized baseline.

The result does not establish failure probability, accuracy, precision, specificity, false-positive rate, ROC AUC, or verified healthy-negative performance. Future advanced-model development must remain restricted to governed training and validation evidence until its own method is frozen.

## Governed Advanced-Model Comparison Contract

Status: Implemented, tested, validated, committed, pushed, and synchronized on August 5, 2026.

### Implemented Scope

Created and validated:

```text
config/metropt3_advanced_model_comparison.json
docs/advanced_model_comparison_method.md
src/predictive_maintenance/analysis/advanced_model_comparison.py
tests/test_advanced_model_comparison.py
```

The contract validator:

- preserves the finalized robust-distance baseline as an immutable reference;
- prohibits baseline test evidence from candidate design, feature selection, preprocessing, hyperparameter selection, threshold selection, or validation ranking;
- authorizes only `sklearn.ensemble.IsolationForest` for this bounded comparison;
- requires the same frozen 48-feature set for all candidates;
- restricts fitting and threshold derivation to eligible training-reference rows;
- restricts candidate ranking to validation evidence;
- freezes a deterministic lexicographic selection rule;
- keeps advanced-model test access disabled;
- performs no model fitting, scoring, alarm generation, candidate selection, or advanced test evaluation during contract validation.

### Bounded Candidate Definition

```text
contamination: auto
bootstrap: false
random_state: 42
n_jobs: -1
n_estimators: 100, 200
max_samples: 1024, 4096
max_features: 0.5, 1.0
candidate count: 8
```

Each candidate threshold must be the 0.995 quantile of that candidate's eligible training-reference scores and must remain frozen before validation.

### Deterministic Validation Selection

Candidates are ranked lexicographically using validation evidence only:

1. maximize documented-event coverage;
2. minimize mean first-alarm latency for covered events;
3. minimize alarms per 24 observed hours;
4. minimize deterministic candidate-complexity rank.

Alarm burden is operational evidence, not a false-positive rate. Accuracy, precision, population sensitivity, specificity, false-positive rate, ROC AUC, and failure-probability claims remain unsupported.

### Verification Evidence

```text
JSON validation: passed
Python compilation: passed
Focused tests: 22 passed in 0.23 seconds
Complete repository suite: 151 passed in 3.39 seconds
Processing status: advanced_model_comparison_contract_validated
Candidate family: isolation_forest
Candidate count: 8
Advanced test partition locked: true
```

### Governed Generated Artifact

```text
outputs/metropt3_advanced_model_comparison_contract_report.json
File size: 4,851 bytes
Ignore rule: .gitignore line 31, outputs/*
```

The generated report remains excluded from Git.

### Repository Evidence

```text
Commit: 26f0024481f59dec65d1c0cd502d2b8e9d249762
Message: Define governed advanced-model comparison contract
Scope: four new professional files
Local HEAD and origin/main: matched after push
```

### Engineering Interpretation

The comparison rules were fixed before model fitting. This prevents candidate-family expansion, validation-threshold tuning, test-driven selection, and unfair feature or preprocessing changes after results are observed.

The contract does not demonstrate advanced-model performance. The next milestone is the governed eight-candidate Isolation Forest training-and-validation workflow. Advanced-model test evaluation remains locked.


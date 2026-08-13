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
- Final verified repository commit: `be37ff7c771ddb0e01b833c212bffdaa3a56b42f`
- Final verification commit message: `Record final release verification`
- Release-hardening implementation commit: `78f747a252ebaf3644f9998840ab13ea02cd958e`
- Final local and remote commit identity: matched at `be37ff7c771ddb0e01b833c212bffdaa3a56b42f`
- Complete repository test suite: 365 passing tests
- Advanced-model held-out access: consumed exactly once; no additional held-out scoring occurred
- Governed technical-knowledge corpus: 3 sources, 354 deterministic chunks, provenance validation passed
- Governed retrieval layer: reproducible TF-IDF keyword retrieval plus 128-dimensional LSA embeddings and bounded hybrid fusion
- Governed answer layer: deterministic reranking, provenance-preserving citations, bounded evidence assembly, and explicit insufficient-evidence refusal
- Governed evaluation layer: frozen-artifact validation with separate retrieval-quality, citation-correctness, faithfulness, answer-usefulness, failure-case, and limitation reporting
- Integrated application layer: loopback-only FastAPI contracts for frozen-model prediction, governed retrieval, citation-grounded answers, bounded SQLite persistence, structured operational events, readiness checks, monitoring counters, and sanitized failure behavior
- Reproducible container execution: pinned Dockerfile frontend and Python 3.14.6 slim-bookworm base image, fully pinned container runtime dependency closure, deny-all build-context allowlist, unprivileged runtime user, read-only root filesystem, dropped Linux capabilities, no-new-privileges, loopback-only host publication, read-only governed artifact mounts, and Docker-managed writable application state
- Professional integrated demonstration: self-contained local prediction, knowledge/evidence, and operations workspaces over the existing governed FastAPI path; fixed asset routing; same-origin content-security policy; no remote UI dependencies or browser persistence
- Release-candidate hardening: non-destructive 15-check audit over frozen identities, governed artifacts, professional release documentation, local security controls, and interface self-containment
- Professional release package: finalized data card, evaluation summary, deployment guide, portfolio/interview guide, release-candidate checklist, and README documentation index using verified evidence only
- Container verification evidence: clean no-cache build passed; exact governed runtime dependency versions matched; image artifact/secret exclusion passed; health/readiness, prediction schema, retrieval, grounded-answer, exact-equipment refusal, and loopback network boundaries passed
- Release-hardening implementation CI: GitHub Actions run `31660678645` completed successfully on exact commit `78f747a252ebaf3644f9998840ab13ea02cd958e`; Python compilation, the 365-test repository suite, and dependency consistency passed
- Exact-equipment instructions require governed exact-equipment evidence
- Generated datasets, downloaded knowledge sources, normalized text, chunks, retrieval indexes, reports, figures, model artifacts, and temporary files: excluded from Git under governed ignore rules

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

Target Governance established the governed validation framework without creating row-level labels. Verified Target Governance implementation commit: `607bac4` (`Implement governed target definition and temporal evaluation`). The Target Governance status record documentation commit was `d9fc5b9`.

### Exact MetroPT-3 Failure-Event Provenance

Failure-Event Provenance replaced the ambiguous design placeholder with four intervals documented by the exact 2020 MetroPT-3 UCI dataset source.

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

Failure-Event Provenance implementation changes:

- Upgraded the governed specification to schema version 2.
- Added exact dataset source identifiers, access dates, dataset-match controls, and source-conflict records.
- Added `docs/failure_event_provenance.md`.
- Updated the method documentation to distinguish the 2020 UCI failure records from later MetroPT research data.
- Removed the invented prediction-window placeholder; prediction-window count is now zero.
- Preserved the four records as event metadata rather than row-level labels.
- Strengthened target-definition tests from 9 to 16.

Verified Failure-Event Provenance validation report:

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

Verified Failure-Event Provenance testing:

- Python syntax compilation: passed
- Focused target-definition tests: 16 passing
- Complete repository test suite: 42 passing
  - 12 data-quality tests
  - 7 Parquet and DuckDB tests
  - 7 exploratory-analysis tests
  - 16 target-definition tests
- Failures: 0
- Errors: 0

Verified Failure-Event Provenance implementation commit and push:

- Commit: `4ab2333b2684447e62fa45fc6e0fe0aaf989b863`
- Message: `Document MetroPT-3 failure-event provenance`
- Scope: 5 files changed, 330 insertions, 73 deletions
- New file: `docs/failure_event_provenance.md`
- Push: `origin/main` advanced from `d9fc5b9` to `4ab2333`
- End-of-implementation synchronization: local `HEAD` and `origin/main` matched
- End-of-implementation working tree: clean

### Governed Row-Level Target Materialization

Target Materialization implemented the audited translation from governed event metadata to row-level target states without inventing a negative class or crossing observation gaps.

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

Verified Target Materialization implementation commit and push:

- Commit: `c16a9465fed7755d1b3a86ab84f489b83d6a886f`
- Message: `Materialize governed MetroPT-3 target states`
- Scope: 4 files changed, 994 insertions, 4 deletions
- Push: `origin/main` advanced from `a7a8bb7` to `c16a946`
- Local `HEAD` and `origin/main` matched after fetch verification
- End-of-implementation working tree: clean


### Leakage-Safe MetroPT-3 Feature Engineering

Feature Engineering implemented the reproducible feature layer over the governed sensor history and row-level target states.

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

Baseline Evaluation Contract defined and validated the population, chronology, leakage controls, future transparent baseline, permitted metrics, and prohibited claims before any baseline fitting or performance reporting.

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

`ENGINEERING_LOG.md` must be updated for each completed engineering milestone with verified files, validations, evidence, architecture decisions, commit and push state, repository state, and one exact next milestone.

### Governed Technical Knowledge Corpus and Deterministic Chunking

Implemented the bounded technical-document foundation used by later retrieval and citation-grounded answering.

Committed artifacts:

```text
config/knowledge_corpus.json
docs/knowledge_corpus_method.md
src/predictive_maintenance/knowledge/__init__.py
src/predictive_maintenance/knowledge/corpus.py
tests/test_knowledge_corpus.py
requirements.txt
```

Governance and processing controls:

- bounded corpus membership is declared before ingestion;
- source identity, publisher, source URL or DOI, retrieval identity, license or usage status, equipment relevance, local path, and source classification are preserved;
- exact dataset/project evidence remains distinguishable from authoritative general compressed-air guidance;
- the related Scientific Data MetroPT article is explicitly scoped as a 2022 collection and is not assumed to be byte-, schema-, or time-period-identical to the 2020 UCI MetroPT-3 corpus used by this project;
- the U.S. Department of Energy compressed-air sourcebook is classified as authoritative general guidance and is never represented as the exact MetroPT equipment manual;
- PDF extraction uses `pypdf==6.14.2`; HTML extraction uses the Python standard-library parser;
- normalization is deterministic and conservative, including Unicode NFKC normalization and whitespace normalization without semantic rewriting;
- chunks are bounded to 220 words with 40-word overlap and a 20-word preferred minimum tail;
- PDF page boundaries are preserved as provenance units and chunks do not cross extraction-unit boundaries;
- chunk identifiers and chunk-text checksums are deterministic;
- every chunk retains source identity, classification, equipment-relevance boundary, retrieval identity, source checksum, locator, ordering fields, word count, and chunk checksum;
- source-content completeness gates require minimum extracted word counts and stable required markers before chunking;
- prior generated corpus evidence is invalidated before a refresh so a failed run cannot leave an older successful report or chunk file that could be mistaken for current evidence;
- downloaded documents, normalized text, chunks, and runtime reports remain under governed ignored paths.

Verified live corpus evidence:

```text
Corpus ID: predictive_maintenance_technical_knowledge_v1
Governed sources: 3
Deterministic chunks: 354
Provenance validation: passed
Chunk corpus SHA-256: 4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d
```

Source-level evidence:

```text
metropt3_uci_description
  Classification: exact_dataset_source
  Extracted words: 410
  Extraction units: 3
  Chunks: 3
  Source SHA-256: b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127

metropt_scientific_data_2022
  Classification: exact_dataset_source
  Extracted words: 3,677
  Extraction units: 1
  Chunks: 21
  Source SHA-256: d3d7d2a097b1c19f1e77017da7f5d96e1a93ec7fd05ace23782a6753ec77bf3d

doe_compressed_air_sourcebook
  Classification: authoritative_general_reference
  Extracted words: 53,645
  Extraction units: 114
  Chunks: 330
  Source SHA-256: 3280284235b8daef10f7d9e6a21aada90d7b804b805cc9ef842903aeca009c22
```

The independently calculated SHA-256 of `data/interim/knowledge/chunks.jsonl` matched the report value exactly.

Verified correction record:

- The first live Scientific Data retrieval produced only one short chunk because the publisher endpoint returned incomplete landing/interstitial content. The workflow was corrected to use the complete PubMed Central archival full text while preserving the Scientific Data publisher identity and DOI, and source-completeness gates were added.
- A subsequent run correctly stopped because a UCI PDF narrative phrase was too brittle as an extraction marker. The rule was replaced by a stable `MetroPT` identity marker plus a minimum extracted-word threshold.
- Failed-run evidence invalidation was added so stale successful reports or chunk files cannot survive a failed refresh and be mistaken for current evidence.
- Regression tests cover both source-completeness failures and stale-evidence invalidation.

Verified testing and repository state:

```text
Focused knowledge-corpus tests: 33 passing
Complete repository suite: 236 passing
Complete-suite elapsed time: 4.42 seconds
pip check: no broken requirements
Whitespace check before commit: passed
Implementation commit: 3909a985259ccbc42a01b99b12cd18fa3b3a724a
Commit message: Build governed technical knowledge corpus
Local HEAD and origin/main after push: matched
Working tree after implementation push: clean
```

Generated corpus evidence remains excluded from Git:

```text
data/raw/knowledge/
data/interim/knowledge/
outputs/knowledge_corpus_report.json
```

### Governed Embeddings and Hybrid Knowledge Retrieval

Implemented a bounded reproducible retrieval layer over the verified governed chunk corpus.

Committed artifacts:

```text
config/knowledge_retrieval.json
docs/knowledge_retrieval_method.md
src/predictive_maintenance/knowledge/retrieval.py
tests/test_knowledge_retrieval.py
```

Retrieval contract and controls:

- the input corpus is frozen to 354 governed chunks with SHA-256 `4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d`;
- keyword representation uses scikit-learn TF-IDF with one- and two-word features, L2 normalization, sublinear term frequency, and a 16,000-feature vocabulary cap;
- vector representation uses deterministic 128-component latent semantic analysis with randomized `TruncatedSVD`, `random_state=42`, and seven iterations;
- hybrid fusion weights vector similarity at `0.65` and keyword similarity at `0.35`;
- candidate generation is bounded to 30 candidates from each retrieval path, with default `top_k=8` and maximum `top_k=12`;
- saved indexes are rejected when the retrieval configuration or governed chunk corpus does not match the identities used at index construction;
- retrieval results preserve source ID, title, publisher, URL, DOI, classification, equipment relevance, license or usage status, retrieval identity, scope note, source checksum, locator, ordering fields, word count, chunk checksum, and chunk text;
- reranking, citation rendering, answer generation, and insufficient-evidence refusal remain outside this retrieval layer;
- generated retrieval artifacts remain under ignored `data/interim/` and `outputs/` paths.

Verified live retrieval evidence:

```text
Corpus ID: predictive_maintenance_technical_knowledge_v1
Chunk count: 354
Corpus SHA-256: 4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d
Retrieval ID: predictive_maintenance_hybrid_retrieval_v1
Configuration fingerprint: 979eebb3e9fb115d10e70b55fbfaea03f375803e006091788eb6a673c68c37c1
Keyword vocabulary size: 16000
Embedding method: lsa_tfidf
Embedding dimension: 128
Explained-variance-ratio sum: 0.5937216799895125
Index signature: 96bd60cb61a6782245a36e23f3e72b3db37a20eef00f93f70afc589b774d3a09
Vocabulary signature: f8b192db56a996df7486c8051a92edf5112830cd2cf1f0a165d52809f5069805
Document-embedding SHA-256: 6dacfa4a4f343a6ec55231a421e15c7a542ce4fd7ac91db5ba47f36d3df7e716
SVD-components SHA-256: 8e0462a2c9add27380c5f186f93cc9fae18e9b3d0f581af140af1247e10e2dc9
```

Determinism checks after a second rebuild all matched exactly:

```text
Index signature: matched
Document-embedding checksum: matched
SVD-components checksum: matched
Vocabulary signature: matched
```

Controlled retrieval smoke evidence:

- A MetroPT-focused query returned MetroPT exact-dataset sources in all five displayed results, including the UCI MetroPT-3 description.
- A compressed-air maintenance query returned the U.S. Department of Energy sourcebook in all five displayed results, with classification preserved as `authoritative_general_reference` and page locators preserved.
- These smoke checks verify implementation behavior and provenance boundaries; they are not retrieval-quality evaluation claims.

Verified correction record:

- Windows PowerShell exposed a CLI serialization defect when retrieved evidence contained the Unicode character `∆` and the console attempted `cp1252` encoding.
- CLI JSON output was changed to ASCII-safe JSON escaping while preserving Unicode content after JSON parsing.
- A regression test verifies Unicode evidence round-trips correctly through CLI JSON serialization.

Verified testing and repository state:

```text
Focused retrieval tests: 16 passing
Complete repository suite: 252 passing
Complete-suite elapsed time: 4.65 seconds
pip check: no broken requirements
Whitespace check before commit: passed
Implementation commit: 28dbbcb65c065e2d7fb0ef08320dec2bd72813b6
Commit message: Implement governed hybrid knowledge retrieval
Local HEAD and origin/main after push: matched
Working tree after implementation push: clean
```

Generated retrieval evidence remains excluded from Git:

```text
data/interim/knowledge/retrieval/hybrid_index.joblib
  SHA-256: 2700dac28adfc9a80a9bd28c3af177237d45e845ef94c37cd4e68b421d4442b7

outputs/knowledge_retrieval_report.json
  SHA-256: 5ae4406eba7765c3159ce6d6f7c7600e26bd0bcf1b915732ecdf73d50a46a187
```

## Historical Engineering Workstream Snapshot

The data-engineering and machine-learning workstreams are frozen through governed held-out evaluation. The technical-knowledge workstream is implemented through deterministic source materialization, extraction, normalization, chunking, reproducible keyword/vector representation, bounded hybrid retrieval, deterministic reranking, provenance-preserving citation assembly, and explicit insufficient-evidence refusal.

The active corpus contains three governed sources and 354 deterministic chunks. Source identity, classification, equipment-relevance boundaries, checksums, locators, and chunk text survive retrieval through answer assembly.

Implementation smoke checks verify deterministic behavior and source-governance boundaries. They are not formal claims of retrieval quality, citation correctness, faithfulness, or answer usefulness.

## Subsequent Engineering Milestone

Create a governed retrieval and grounded-answer evaluation set. Evaluate retrieval quality, citation correctness, faithfulness, answer usefulness, failure cases, and limitations separately. Preserve the distinction between implementation smoke checks and formal quality evidence, and do not revise the frozen machine-learning release from retrieval or answer-evaluation results.

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
- reuses the frozen Robust-Distance Validation feature medians, IQRs, and baseline decision without refitting them;
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
config/metropt3_isolation_forest_validation.json
docs/advanced_model_comparison_method.md
docs/isolation_forest_validation_method.md
src/predictive_maintenance/analysis/advanced_model_comparison.py
src/predictive_maintenance/analysis/isolation_forest_validation.py
tests/test_advanced_model_comparison.py
tests/test_isolation_forest_validation.py
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

## Governed Isolation Forest Training and Validation

Status: Implemented, tested, executed, frozen after validation, committed, pushed, and synchronized on August 7, 2026.

### Implemented Scope

Created and validated:

```text
config/metropt3_isolation_forest_validation.json
docs/isolation_forest_validation_method.md
src/predictive_maintenance/analysis/isolation_forest_validation.py
tests/test_isolation_forest_validation.py
```

Updated dependency control:

```text
requirements.txt
scikit-learn==1.8.0
```

The workflow:

- preserves the finalized robust-distance baseline and the frozen Advanced-Model Comparison Contract;
- uses only the predetermined eight `sklearn.ensemble.IsolationForest` candidates;
- uses the same frozen 48-feature set for every candidate;
- fits every candidate only on eligible training-reference rows;
- rejects missing or non-finite candidate inputs rather than fitting replacement preprocessing;
- derives each candidate alarm threshold from the 0.995 quantile of its eligible training-reference scores;
- freezes each candidate and threshold before validation;
- scores validation rows only;
- calculates only governed operational validation evidence;
- selects one candidate using the frozen lexicographic order: maximize documented-event coverage, minimize covered-event mean first-alarm latency, minimize alarms per 24 observed hours, then minimize candidate complexity;
- persists the selected model and validation decision as ignored generated evidence;
- keeps the advanced-model test partition locked.

### Verification Evidence

Dependency validation:

```text
scikit-learn: 1.8.0
duckdb: 1.5.5
pyarrow: 25.0.0
pip check: No broken requirements found
```

Focused controlled test suite:

```text
Command: python -m unittest tests.test_isolation_forest_validation -v
Tests run: 23
Failures: 0
Errors: 0
```

Authoritative complete repository suite:

```text
Command: python -m pytest -q
Tests passed: 174
Failures: 0
Errors: 0
Elapsed time: 4.39 seconds
```

Production training and validation:

```text
Processing status: isolation_forest_validation_completed
Candidate count: 8
Eligible training-reference rows: 734,015
Validation rows scored: 329,624
Test rows scored: 0
Advanced-model test partition locked: true
```

Frozen selected candidate:

```text
Candidate: iforest_ne200_ms4096_mf1p0
n_estimators: 200
max_samples: 4096
max_features: 1.0
contamination: auto
bootstrap: false
random_state: 42
n_jobs: -1
Frozen threshold quantile: 0.995
Frozen threshold: 0.601902290159477
Validation decision status: frozen_after_validation
```

Selected-candidate validation evidence:

```text
Documented-event coverage fraction: 1.0
Mean first-alarm latency for covered events: 11,579 seconds
Alarms per 24 observed hours: 54.17993787237062
Test rows scored: 0
```

These are validation-stage operational metrics. Alarm burden is not a false-positive rate, and the unusualness score is not a failure probability.

### Governed Generated Artifacts

The following generated artifacts were verified and remain excluded from Git:

```text
outputs/metropt3_selected_isolation_forest.joblib
data/processed/metropt3_validation_isolation_forest.parquet
outputs/metropt3_isolation_forest_validation_report.json
```

Verified SHA-256 evidence:

```text
Validation report: c3f7cbb5a19bb6004cc13ccdd04535de8acdc2a8cba635d333345115f9615ced
Selected model: fa23b81d214161488abf601a8b9852f2467347e53d02fca3653a13cdaaaeec1a
Validation-score Parquet: 3312f670178d34b97d914181da68a04c9cd5ef862be155384333ee07c72c24ab
```

Ignore verification:

```text
outputs/metropt3_selected_isolation_forest.joblib -> *.joblib
outputs/metropt3_isolation_forest_validation_report.json -> outputs/*
data/processed/metropt3_validation_isolation_forest.parquet -> data/processed/
```

### Repository Evidence

Implementation commit:

```text
Commit: 8872c5a225f26294ed5a397a40bf3f701992a876
Message: Train and validate governed Isolation Forest candidates
Local HEAD and origin/main: matched after push
```

Verified repository state before this engineering-log update:

```text
Branch: main
Tracking branch: origin/main
Local HEAD: 8872c5a225f26294ed5a397a40bf3f701992a876
Remote origin/main: 8872c5a225f26294ed5a397a40bf3f701992a876
Ahead/behind: none
Working tree after implementation push: clean
```

### Engineering Interpretation

The bounded advanced-model comparison is now frozen after validation. The selected Isolation Forest candidate covered all documented validation events represented by the governed coverage metric, with a mean first-alarm latency of 11,579 seconds and 54.17993787237062 alarms per 24 observed hours.

This evidence is sufficient to freeze the candidate and threshold for the next governed step, but it is not test evidence and does not establish general predictive performance. The advanced-model test partition remains locked. A one-time test comparison may occur only after separate project maintainer authorization and without refitting, threshold revision, feature changes, or candidate reselection.

### Frozen Machine-Learning Release

The governed machine-learning workstream was finalized with one separately authorized held-out evaluation of the already-frozen Isolation Forest candidate.

Verified release evidence:

- Implementation commit: `f4ba8cfb181a238139e1ac031a9960752e587636`
- Complete repository test suite: 203 passing tests
- Frozen candidate: `iforest_ne200_ms4096_mf1p0`
- Frozen threshold: `0.601902290159477`
- Frozen model SHA-256: `fa23b81d214161488abf601a8b9852f2467347e53d02fca3653a13cdaaaeec1a`
- Eligible advanced-model test rows scored: 429867
- Documented events represented in the governed test evidence: 1
- Documented events covered: 1
- Isolation Forest documented-event coverage fraction: 1.0
- Isolation Forest mean first-alarm latency for covered events: 218.0 seconds
- Isolation Forest alarms per 24 observed hours: 69.86256461984617
- Robust-distance baseline documented-event coverage fraction: 1.0
- Robust-distance baseline mean first-alarm latency for covered events: 15804.0 seconds
- Robust-distance baseline alarms per 24 observed hours: 94.19240953221535
- Advanced-model test report SHA-256: `fc36bb22f37c3431f3f645804e8b4d6fba7c67ba7916d373f4eb9540f4c1552a`
- Advanced-model test-score Parquet SHA-256: `578cf1fff7d4a9fceef995bb14f1462008bc49ad7ee6b13ee0b8bf96a61712f8`
- Advanced-model test access: consumed exactly once by the governed release evaluation
- Test-driven refit, feature change, threshold change, or candidate reselection: none
- Robust-distance detector: retained as the finalized transparent benchmark
- Generated model, score Parquet, and JSON evidence: excluded from Git under governed ignore rules

The machine-learning release documentation includes the model card, held-out evaluation report, data/feature governance summary, architecture, reproducibility commands, and updated README. That technical-document corpus milestone was subsequently implemented and verified before the current grounded-answer work.

## Governed Reranking and Citation-Grounded Answer Assembly

Status: Implemented, tested, smoke-validated, committed, pushed, and synchronized.

### Implemented Scope

Created and validated:

```text
config/knowledge_grounding.json
docs/knowledge_grounding_method.md
src/predictive_maintenance/knowledge/grounding.py
tests/test_knowledge_grounding.py
```

The implementation preserves the existing 354-chunk governed corpus and governed retrieval index, adds deterministic reranking and stable source citations, bounds evidence assembly, and refuses equipment-specific instructions unless exact equipment evidence exists.

### Verification Evidence

```text
Focused grounding tests: 24 passing
Complete repository suite: 276 passing
Grounding smoke-report status: passed
Grounding report SHA-256: a31b3d4f0564aeb713350f776da357db1d8f179378e18562c2c8b9d3f82429c6
Implementation commit: 39ea32bc649ecce5b539dbacdc2a35ed8c6a1105
HEAD and origin/main: matched
```

Smoke validation covers dataset-context answering, authoritative general compressed-air guidance, and explicit refusal of manufacturer-specific MetroPT compressor instructions when no exact equipment manual is governed.

The smoke report is implementation evidence only. Formal retrieval quality, citation correctness, faithfulness, answer usefulness, failure cases, and limitations remain the next separately governed evaluation milestone.

### Governance Boundaries

- Source identity, classification, locators, and checksums survive retrieval through answer assembly.
- General authoritative guidance is never relabeled as exact MetroPT equipment guidance.
- The existing retrieval index is not rebuilt or modified by this stage.
- No external reranker, LLM API, secret, or remote inference service is introduced.
- Insufficient evidence produces an explicit refusal rather than unsupported equipment-specific instructions.

## Repository Verification and Governance Hardening

Status: Implemented, regression-tested, CI-verified, branch-protected, committed, pushed, and synchronized.

### Implemented Scope

- Updated GitHub Actions to the Node 24-compatible official `actions/checkout@v6` and `actions/setup-python@v6` action majors.
- Replaced the open-ended development/test dependency range with an exact CPython 3.14 verification dependency set in `requirements-dev.txt`.
- Pinned NumPy below the 2.5 deprecation boundary that produced the previously observed third-party `joblib.numpy_pickle` warning while preserving the frozen runtime model and evaluation boundaries.
- Removed redundant `.gitkeep` placeholders from nonempty or unused repository directories while preserving `outputs/.gitkeep`, which is required by the governed output ignore rule.
- Enabled `main` branch protection with the `Python verification` status check required for protected changes, force pushes disabled, and branch deletion disabled. Administrator bypass remains available so the current single-maintainer workflow is not blocked.
- Preserved all historical commits and verified SHAs; no history rewrite occurred.
- No license was added because repository licensing remains an explicit maintainer legal choice rather than an automatic engineering change.

### Verification Evidence

```text
Implementation commit: 89104d101f574f422c45be6d7ef7325ef76229d8
GitHub Actions run: 31285828469
Complete repository suite: 278 passing tests
Pytest warning count in governed CI verification: 0
Dependency consistency: no broken requirements
Production Python modules changed by this hardening milestone: none
Held-out model evaluation rerun: no
Frozen model, feature set, threshold, corpus, and retrieval index changed: no
```

### Engineering Interpretation

Repository verification is now reproducible across fresh CPython 3.14 environments, CI no longer relies on Node 20-targeted action majors, and the default branch has explicit protection against unsafe force-push or deletion behavior. The machine-learning release and governed knowledge artifacts remain unchanged.

The next governed capability milestone remains retrieval and grounded-answer evaluation, with retrieval quality, citation correctness, faithfulness, answer usefulness, failure cases, and limitations reported separately.

## Governed Retrieval and Grounded-Answer Evaluation

Status: Implemented, regression-tested, evaluated against frozen artifacts, CI-verified, committed, pushed, and synchronized on August 9, 2026.

### Implemented Scope

Created and validated:

```text
config/knowledge_evaluation.json
docs/knowledge_evaluation_method.md
src/predictive_maintenance/knowledge/evaluation.py
tests/test_knowledge_evaluation.py
```

The governed evaluator:

- uses a fixed twelve-case evaluation set spanning MetroPT dataset questions, authoritative general compressed-air questions, and exact-equipment refusal cases;
- verifies the exact frozen corpus, retrieval-index, and grounding identities before evaluation;
- evaluates retrieval before reranking and answer assembly;
- reports retrieval quality, citation correctness, faithfulness, answer usefulness, failure cases, and limitations separately;
- preserves source-classification boundaries between the exact 2020 UCI MetroPT-3 documentation, related MetroPT research, and authoritative general compressed-air guidance;
- treats exact-equipment requests as refusal cases because no governed exact-equipment manual is present;
- does not rebuild or retune the corpus, retrieval index, reranking configuration, or grounding behavior from evaluation results;
- invalidates stale generated evaluation evidence before a new run;
- introduces no external LLM judge, remote inference service, secret, or network-dependent evaluator.

### Verification Evidence

Local focused evaluation tests:

```text
Tests passed: 30
Failures: 0
Errors: 0
```

Local complete repository regression suite:

```text
Tests passed: 308
Failures: 0
Errors: 0
Dependency consistency: no broken requirements
```

GitHub Actions verification:

```text
Implementation commit: d11247a6a26d8be7b5a93fecd4eccfddcf8f3c22
Commit message: Add governed RAG evaluation
CI workflow run: 31349968358
Required job: Python verification
Exact checked-out commit: d11247a6a26d8be7b5a93fecd4eccfddcf8f3c22
Python compilation: passed
Complete repository suite: 308 passed
Dependency consistency: no broken requirements
CI conclusion: success
```

### Governed Evaluation Evidence

Generated report:

```text
outputs/knowledge_evaluation_report.json
SHA-256: 32d906841726df4779fa1250cdcd96e0763fb6083c5de7bb4461fa6efc63cb00
Evaluation ID: predictive_maintenance_rag_evaluation_v1
Evaluation status: completed
Evaluation cases: 12
Measured failure cases: 3
```

Retrieval quality:

```text
Labeled source-retrieval cases: 8
Source Hit@1: 0.625
Source Hit@3: 0.625
Source Hit@5: 0.625
Mean reciprocal rank: 0.6458333333333334
Top-1 expected source-classification rate: 1.0
Exact-equipment boundary with no exact-equipment source retrieved: 1.0
```

Citation correctness:

```text
Citations emitted: 40
Traceable citations: 40
Citation traceability rate: 1.0
Answered-case marker coverage rate: 1.0
Source-scope alignment rate: 1.0
```

Faithfulness:

```text
Cited claims: 40
Supported cited claims: 40
Supported cited-claim rate: 1.0
Exact-equipment refusal-boundary pass rate: 1.0
```

Answer-usefulness proxy:

```text
Expected-status rate: 1.0
Expected-reason rate: 1.0
Expected-intent rate: 1.0
Mean concept coverage for answerable cases: 0.9375
Usefulness-proxy pass rate: 1.0
```

Measured retrieval failure cases:

```text
dataset_air_production_unit: retrieval_source_miss_at_5
dataset_sampling: retrieval_source_miss_at_5
dataset_signals: retrieval_source_miss_at_5
```

A read-only follow-up retrieval diagnosis preserved these failures rather than retuning against them. For the Air Production Unit query, the exact UCI MetroPT-3 documentation appeared at rank 6. For the sampling and signal queries, the exact UCI source was absent from the top 12 while the related 2022 MetroPT Scientific Data source dominated the rankings. The related source remains explicitly distinct from the exact 2020 UCI MetroPT-3 documentation.

### Frozen-Artifact Preservation

```text
Governed chunk corpus SHA-256:
4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d

Frozen hybrid retrieval-index SHA-256:
2700dac28adfc9a80a9bd28c3af177237d45e845ef94c37cd4e68b421d4442b7

Corpus rebuilt: no
Retrieval index rebuilt: no
Retrieval parameters retuned from evaluation evidence: no
Grounding parameters retuned from evaluation evidence: no
Held-out machine-learning evaluator rerun: no
```

The generated evaluation report remains excluded from Git under the existing `outputs/*` ignore rule.

### Engineering Interpretation

The evaluation demonstrates strong structural citation traceability, extractive faithfulness, source-scope citation alignment, expected answer/refusal behavior, and deterministic usefulness-proxy performance on the bounded governed set. It also exposes a concrete source-specific retrieval limitation: the frozen hybrid retriever does not place the exact UCI MetroPT-3 documentation within the top five for three UCI-specific questions.

These results are descriptive evidence for the current bounded three-source corpus and deterministic RAG implementation. They do not establish broad production quality, exhaustive factual coverage, safety certification, or business impact.

The next governed capability milestone is the combined application foundation: prediction and retrieval APIs, persistence, and operational and security controls.

## Integrated Application Foundation

Status: Implemented, regression-tested, committed, pushed, and CI-verified.

Implemented documented loopback-only prediction, retrieval, and grounded-answer API contracts; bounded SQLite persistence; structured operational events; health/readiness checks; local monitoring counters; configuration and secret-handling controls; sanitized failure behavior; and integration tests. The frozen Isolation Forest model, threshold, feature set, governed corpus, retrieval index, and grounding behavior were consumed read-only and were not rebuilt, refit, or retuned.

Windows validation exposed SQLite handle retention during the first local regression attempt. The corrected implementation explicitly closes transaction-scoped SQLite connections, adds a closure regression test, and uses the supported Starlette HTTP test client dependency. The corrected validation completed with warnings treated as errors.

```text
Implementation commit: 7df00d0dcb14360c7f98d42403d6cc0b36573f30
Commit message: Add governed application foundation
CI workflow run: 31352440290
Focused application tests passed: 35
Complete repository tests passed locally: 343
Complete repository tests passed in CI: 343
Dependency consistency: no broken requirements
Held-out evaluator rerun: no
Frozen ML/RAG artifacts changed: no
Public deployment claimed: no
```

## Reproducible Container Execution

Status: Implemented, clean-build verified, committed, pushed, and CI-verified.

The integrated local application is now containerized without changing the frozen machine-learning or governed RAG behavior. The deployment remains a bounded local demonstration and does not claim public production deployment.

Implemented repository artifacts:

- `.dockerignore`
- `Dockerfile`
- `compose.yaml`
- `requirements-container.txt`
- `docs/container_execution.md`
- `tests/test_container_execution.py`

Verified container controls:

- Dockerfile frontend pinned by digest.
- Python base image pinned to `python:3.14.6-slim-bookworm` by digest.
- Container runtime dependency closure pinned exactly and aligned to the governed CPython 3.14 verification environment.
- Clean `--no-cache` build reproduced the governed runtime versions, including NumPy `2.4.6`, SciPy `1.18.0`, scikit-learn `1.8.0`, Starlette `1.3.1`, FastAPI `0.139.2`, Pydantic `2.13.4`, and Uvicorn `0.51.0`.
- `.dockerignore` uses a deny-all policy with a narrow allowlist for runtime source, configuration, Docker files, and dependency contracts.
- Generated model, corpus, retrieval-index, database, secret, environment, repository-history, test, and documentation artifacts are excluded from the image build context unless explicitly required for runtime source/configuration.
- Governed generated ML/RAG artifacts are mounted read-only and are not baked into the image.
- Writable application state uses the Docker-managed `application_state` volume.
- Container runs as UID/GID `10001:10001`, uses a read-only root filesystem, drops all Linux capabilities, enables `no-new-privileges`, and uses writable `/tmp` tmpfs.
- Uvicorn binds `0.0.0.0:8000` only inside the isolated container namespace; Docker publishes the service only as host loopback `127.0.0.1:8000`.
- `/health/live` and `/health/ready` passed with frozen model, chunk-corpus, and retrieval-index identities matched.
- The frozen prediction schema remained 48 features.
- Retrieval smoke verification returned governed evidence.
- Citation-grounded answer smoke verification returned citations.
- Exact-equipment requests preserved the `no_exact_equipment_evidence` refusal boundary.
- No frozen machine-learning or RAG artifact was rebuilt, refit, retuned, or reevaluated.
- The consumed advanced-model held-out evaluator was not rerun.

Container correction record:

- Initial functional container verification passed, but the clean build exposed unpinned transitive dependency resolution.
- The corrected implementation added `requirements-container.txt`, pinned the full runtime dependency closure, pinned the Dockerfile frontend digest, and expanded the static container-contract tests from 8 to 10.
- Focused container suite: 10 passing tests.
- Complete local repository suite: 353 passing tests.

Verified repository and CI evidence:

```text
Implementation commit: 05d002da9659c6fb434e8cd6bb06a647bff23e1e
Commit message: Add reproducible container execution
Implementation parent: 14d727be74ab1f598e58e20282a1a7b4b8b0f8c7
GitHub Actions run: 31455513766
Python verification: success
CI repository tests: 353 passed
CI dependency consistency: no broken requirements
Local/remote implementation identity: matched
Held-out evaluator rerun: no
Frozen ML/RAG artifacts changed: no
Public production deployment claimed: no
```

The next core milestone is the bounded professional demonstration interface and functional integration target.
## Professional Demonstration and Functional Integration

Status: Implemented, regression-tested, committed, pushed, and CI-verified.

The bounded local release candidate now serves a self-contained professional browser interface over the existing prediction, retrieval, grounded-answer, readiness, metrics, and review-record APIs. The interface presents model outputs with their unusualness boundary, preserves citation/source/locator evidence, keeps exact-equipment refusal visible, and introduces no alternate inference or retrieval path.

Verified controls and evidence:

- Prediction workspace loads the exact frozen 48-feature schema and calls the frozen scoring API.
- Knowledge workspace calls governed retrieval and grounded-answer endpoints and displays citations and provenance.
- Operations workspace displays readiness, bounded local counters, and local review counts.
- UI assets use no CDN, remote font, analytics, external inference service, local storage, or session storage.
- Fixed asset routing and same-origin content-security policy preserve the bounded local application scope.
- Documented module startup: warning-free with warnings treated as errors.
- Focused UI/API tests: 20 passing.
- Complete repository suite: 362 passing tests.
- Dependency consistency: no broken requirements.
- Implementation commit: `9caf2b14633fe922ca4744a49f831296e92d4c35`.
- Implementation CI run: `31656697370`.
- Frozen ML/RAG artifacts changed: no.
- Held-out evaluator rerun: no.
- Public production deployment claimed: no.

The next core milestone is combined release hardening, verified defect correction, and the portfolio/career release package.

## Release-Candidate Hardening and Professional Project Package

Status: Implemented, regression-tested, release-audited, clean-build and live-path verified, committed, pushed to the release branch, and CI-verified.

The release-hardening milestone completed the combined clean-state integration audit and professional release package without changing the frozen model, threshold, feature schema, governed corpus, retrieval index, reranking, grounding behavior, API contracts, Docker boundary, or interface behavior.

Implemented repository scope:

- Added `src/predictive_maintenance/release_audit.py`, a non-destructive release audit for frozen identities, required governed artifacts, professional release documents, local security controls, and self-contained interface assets.
- Added `tests/test_release_audit.py` covering the passing release state, missing governed artifacts, and prohibited remote interface dependencies.
- Added `docs/data_card.md`, `docs/deployment_guide.md`, `docs/evaluation_summary.md`, `docs/portfolio_interview_guide.md`, and `docs/release_candidate_checklist.md`.
- Updated `README.md` with the release-audit command and final professional documentation index.
- Preserved the existing model card, evaluation report, machine-learning architecture, system architecture, reproducibility documentation, and professional demonstration guidance.

Release-document correction record:

- Functional, regression, dependency, release-audit, Docker, live-path, and visual checks passed; the staged whitespace gate then found one unintended blank line at EOF in each of five new Markdown documents.
- The correction removed only those five unintended EOF blank lines. Executable payloads, technical claims, verified behavior, frozen artifacts, and evaluation evidence remained unchanged.
- Final staged professional-content and whitespace checks passed before commit.

Verified local release evidence:

```text
Focused release-audit tests: 3 passed
Complete repository suite: 365 passed
Dependency consistency: no broken requirements
Release audit: 15 of 15 checks passed
Release-audit report: outputs/release_candidate_audit.json
Generated release-audit report committed: no; ignored under governed output controls
Held-out machine-learning evaluator executed: no
Model or retrieval index rebuilt: no
Frozen ML/RAG artifacts changed: no
```

Verified container and live-path evidence:

- Docker Desktop server `29.7.2` became available through the registered Windows application and the `desktop-linux` context.
- Compose contract validation and a clean no-cache image build passed against the pinned Python 3.14.6 slim-bookworm base and exact container dependency closure.
- The container ran as UID/GID `10001:10001`, published only `127.0.0.1:8000`, and reached ready status.
- Liveness, readiness, the frozen 48-feature schema, candidate `iforest_ne200_ms4096_mf1p0`, and threshold `0.601902290159477` matched.
- Synthetic prediction path verification returned a scored response and was explicitly treated as interface-path evidence rather than performance evidence.
- Governed retrieval returned five results; the grounded-answer path returned three citations.
- Exact-equipment requests returned `insufficient_evidence` with reason `no_exact_equipment_evidence`, used zero exact-equipment evidence chunks and no citation markers in the refusal answer, and preserved contextual citation metadata without presenting it as exact-equipment evidence.
- Metrics and bounded application-history persistence checks passed.
- Manual professional visual review confirmed the three workspaces were readable and free of overlap.
- Temporary containers and networks were removed, the application-history volume was preserved, and host port 8000 was released.

Verified repository and CI evidence:

```text
Implementation commit: 78f747a252ebaf3644f9998840ab13ea02cd958e
Implementation parent: 9c5fda656ba34ee8044647b318b7aa320b2c1c47
Repository files changed: 8
Insertions: 587
Deletions: 4
Draft pull request: #1
GitHub Actions run: 31660678645
Required job: Python verification
CI conclusion: success
CI compilation: passed
CI regression suite: passed
CI dependency consistency: passed
```

Final clean-state verification and formal project closure were completed on August 13, 2026.
## Final Release Verification

Verified on 2026-08-13 from synchronized release baseline `63115cd7c808dac7bde7703917cff735cf3a06e1`.

- Complete repository test suite: 365 passing tests.
- Dependency consistency (`pip check`): passed with no broken requirements.
- Frozen model/RAG artifact integrity: all five governed SHA-256 identities matched.
- Clean-state repository verification: passed on synchronized main with a clean working tree.
- Clean Docker and reproducible-startup verification: passed clean --pull --no-cache build, exact dependency verification, image exclusion, loopback-only startup, and normal shutdown.
- Live prediction/retrieval/citation/refusal/metrics/history verification: passed readiness, frozen 48-feature prediction, governed retrieval, citation-grounded answer, exact-equipment refusal, metrics, and bounded history.
- Ignored-artifact, release-documentation, limitation, and future-extension audit: passed required release-document, ignored-artifact, tracked-file safety, limitations, and future-extension boundary checks.
- Verification note: No held-out evaluator was rerun. No frozen ML/RAG artifact, threshold, feature schema, corpus, index, reranking, or grounding behavior was changed.

The verified release remains a bounded local professional demonstration. No public-production, business-impact, equipment-specific, or unsupported reliability claims are made. Formal project closure was completed on August 13, 2026; no core engineering work remains.

# Engineering Log

## Project

**Intelligent Predictive Maintenance and Technical Knowledge Assistant**

## Purpose

This document records verified implementation milestones, technical decisions, repository changes, and upcoming engineering work.

Only completed and validated work is listed as implemented. Planned capabilities remain identified as future milestones until they are developed and tested.

## Implemented Milestones

### Repository Foundation

* Initialized the local Git repository
* Established `main` as the default branch
* Connected the local repository to GitHub
* Published the public repository at `MAndersonASU/predictive-maintenance-assistant`
* Created the initial project directory structure
* Created the project README
* Verified the local-to-remote Git workflow
* Confirmed that the working tree and remote branch can be synchronized through the documented Git process

### Repository Protection

* Configured exclusions for Python caches and virtual environments
* Excluded environment-variable files, credentials, private keys, and certificates
* Excluded raw, interim, and processed datasets from Git
* Excluded generated outputs, local databases, model artifacts, logs, and analysis caches
* Verified representative ignore rules using `git check-ignore`
* Confirmed that no secret-related filenames are tracked by Git
* Confirmed that the generated Parquet dataset remains under ignored `data/processed/`
* Confirmed that generated conversion metadata remains under ignored `outputs/`

### Source Governance

* Created `data/source_manifest.csv`
* Registered the MetroPT-3 dataset from the UCI Machine Learning Repository
* Recorded the dataset DOI, license, source URL, version, and expected local filename
* Created `docs/document_manifest.csv`
* Registered the primary MetroPT dataset research paper
* Classified the paper as an exact dataset source
* Recorded document licensing, equipment relevance, source URL, and local status
* Validated both manifest files using Python's CSV parser
* Published the source-governance manifests to GitHub

### Governed Data Acquisition

* Implemented deterministic project-relative paths in `src/predictive_maintenance/data/acquire.py`
* Implemented safe streaming download through temporary `.part` files
* Implemented controlled extraction without silent overwrite
* Validated ZIP integrity and expected archive members
* Validated the exact governed 17-column CSV header
* Calculated and recorded SHA-256 checksums
* Updated the governed source manifest atomically
* Preserved the original MetroPT-3 source files under ignored `data/raw/`

Verified source checksums:

* Archive: `aab991a970e58210de853bb8078ce0e63abb4d9412fdc5c79792dae3d8e1721a`
* CSV: `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`
* Dataset PDF: `b00fac0e8899854078309bef4adaa480d82ecf14dc81c5097c3646973e824127`

### Data-Quality Profiling

The immutable MetroPT-3 CSV was profiled with a deterministic, read-only validation workflow implemented in `src/predictive_maintenance/data/data_quality.py` and covered by controlled tests in `tests/test_data_quality.py`.

Verified results:

* 1,516,948 data rows and 17 columns
* Zero row-width mismatches
* Zero exact duplicate rows
* Zero missing values
* Zero timestamp parse failures
* Zero out-of-order or adjacent duplicate timestamps
* Zero numeric-coercion failures
* Zero non-finite numeric values
* Zero invalid supported binary values
* Dominant sampling interval of 10 seconds
* 363 intervals greater than the 15-second gap threshold
* Largest observed gap of 172,918 seconds, approximately 48.033 hours
* Raw source preservation confirmed; the source CSV was not modified

The temporal gaps are recorded as a data-quality limitation. Later time-series analysis must not assume continuous adjacency across these gaps.

### Reproducible Parquet Conversion

Implemented `src/predictive_maintenance/data/parquet_conversion.py` to convert the governed MetroPT-3 CSV into a validated analytical Parquet dataset.

Implemented controls include:

* Deterministic source, output, and metadata paths
* Explicit governed Arrow schema for all 17 source columns
* Preservation of the unnamed source column
* Millisecond Parquet timestamp storage capable of representing the source timestamps exactly
* Streaming CSV reading rather than loading the complete dataset into memory
* Zstandard Parquet compression
* Parquet statistics and stored Arrow schema
* Temporary `.part` output handling
* Protection against unintended destination overwrite
* Source file validation before conversion
* Expected row-count validation
* Parquet metadata row-count validation
* Parquet column-count and schema validation
* Source checksum, size, and modification-time comparison before and after conversion
* Automatic cleanup of incomplete output following a failed conversion
* SHA-256 calculation for the completed Parquet file
* Atomic JSON metadata writing
* Command-line execution with actionable failure messages

Verified conversion results:

* Source rows: 1,516,948
* Parquet rows: 1,516,948
* Source columns: 17
* Parquet columns: 17
* Compression: Zstandard
* Source CSV size: 218,300,507 bytes
* Parquet size: 24,485,606 bytes
* Source CSV SHA-256: `db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`
* Parquet SHA-256: `50f9c0640bde18069270e639d451e79fa1243e917d4ef0e45ac99dc4bf7c80a3`
* Source modification status: unchanged
* PyArrow version: `25.0.0`

The generated Parquet file is stored at:

```text
data/processed/metropt3_air_compressor.parquet
```

The dataset is excluded from Git as a generated analytical artifact.

### DuckDB Analytical Access

Established direct local analytical access to the verified Parquet dataset using DuckDB.

Implemented validation includes:

* In-memory DuckDB connection
* Direct `read_parquet` access without creating a permanent local database
* SQL row-count verification
* SQL schema inspection
* Verification that DuckDB exposes all 17 columns
* Verification that the Parquet timestamp is available as a SQL `TIMESTAMP`
* Explicit handling of DuckDB's `C0` alias for the preserved unnamed source column
* Comparison of DuckDB row and column counts against conversion results

Verified DuckDB results:

* Rows accessible through DuckDB: 1,516,948
* Columns accessible through DuckDB: 17
* DuckDB version: `1.5.5`
* Permanent database file created: no

### Reproducibility Metadata

Generated an atomic JSON report at:

```text
outputs/metropt3_parquet_metadata.json
```

The metadata records:

* Processing status
* UTC generation timestamp
* Source and output paths
* Source and output file sizes
* Source and output SHA-256 checksums
* Row and column counts
* Compression configuration
* CSV streaming block size
* Parquet schema
* Parquet implementation information
* DuckDB schema and row-count validation
* Python, PyArrow, and DuckDB versions
* Source-preservation evidence

The metadata file is excluded from Git as a generated processing artifact.

### Automated Validation

Created `tests/test_parquet_conversion.py` with controlled tests covering:

* Successful CSV-to-Parquet conversion
* Row-count and schema preservation
* Source checksum preservation
* Failed row-count validation and partial-output cleanup
* Missing source handling
* Existing destination protection
* Atomic conversion-metadata writing
* DuckDB row-count and schema access
* Complete conversion-workflow execution

The full repository test suite currently contains:

* 12 data-quality tests
* 7 Parquet and DuckDB tests
* 19 total passing tests

## Repository Verification

| Item                       | Status        |
| -------------------------- | ------------- |
| Local Git repository       | Verified      |
| Default branch             | `main`        |
| Remote name                | `origin`      |
| Remote tracking branch     | `origin/main` |
| GitHub visibility          | Public        |
| Secret-file exclusions     | Verified      |
| Raw-data exclusion         | Verified      |
| Processed-data exclusion   | Verified      |
| Generated-output exclusion | Verified      |
| Dataset manifest           | Implemented   |
| Document manifest          | Implemented   |
| Governed acquisition       | Implemented   |
| Data-quality profiling     | Implemented   |
| Parquet conversion         | Implemented   |
| DuckDB analytical access   | Implemented   |
| Controlled tests           | 19 passing    |

## Architecture Decisions

### Real Industrial Data

The system uses MetroPT-3, a public industrial time-series dataset containing operational measurements from a metro-train Air Production Unit compressor.

### Data Provenance

Every dataset must be registered before ingestion. Source records include publisher information, source URL, access date, version, license, expected local filename, checksum, and processing status.

### Immutable Raw Storage

Original downloaded source files remain under `data/raw/` and are treated as immutable governed inputs.

Derived analytical datasets are created separately and never replace or modify the raw source.

### Columnar Analytical Storage

Parquet is used as the local analytical format because it preserves typed columns, supports compression and column-selective access, and can be queried directly by analytical engines.

The conversion process preserves the governed 17-column source schema and records reproducibility metadata for the generated output.

### DuckDB Access

DuckDB is used for local SQL analysis directly over Parquet.

The current implementation uses an in-memory connection and does not require importing the dataset into a permanent database.

### Timestamp Representation

The CSV reader interprets source timestamps with second-level precision.

The governed Parquet schema stores timestamps as `timestamp[ms]` because Parquet supports millisecond timestamp resolution and can represent every source timestamp exactly without losing information.

### Unnamed Source Column

The first MetroPT-3 CSV column has an empty source name.

The conversion preserves that column in Parquet. DuckDB exposes it as `C0` so it can be referenced through SQL.

### Failure Handling

Partial Parquet and metadata files are written with `.part` suffixes and promoted to their final names only after successful validation.

Failed processing removes temporary outputs rather than leaving incomplete files that appear valid.

### Dependency Reproducibility

The verified local analytical environment is recorded in `requirements.txt`:

```text
duckdb==1.5.5
pyarrow==25.0.0
```

### Document Governance

Technical documents are classified as either:

* Exact dataset documentation
* Authoritative domain reference

Generic compressor documentation will not be represented as the exact equipment manual unless the equipment manufacturer and model are independently verified.

### Public Repository Policy

The public repository contains:

* Source code
* Schemas
* Source manifests
* Documentation
* Tests
* Small representative samples
* Reproducible setup instructions

It does not contain:

* API keys or credentials
* Local `.env` files
* Restricted documents
* Large raw or generated datasets
* Local databases
* Unverified performance claims
* Private development notes

## Current Engineering Workstream

The governed acquisition, data-quality profiling, reproducible Parquet conversion, and DuckDB analytical-access layers are implemented and verified.

The next workstream is documented exploratory analysis of compressor sensor signals and operational states.

Exploratory work must:

* Use the verified Parquet dataset
* Respect the documented temporal gaps
* Avoid assuming uninterrupted sampling across missing intervals
* Separate measured facts from interpretations
* Establish descriptive evidence before target definition or modeling
* Preserve reproducible queries, figures, and analysis configuration

## Planned Technical Milestones

### Data Engineering

* Document representative DuckDB analytical queries
* Measure analytical behavior using the verified Parquet dataset
* Preserve query and visualization reproducibility
* Record analytical limitations before modeling

### Machine Learning

* Perform exploratory analysis of compressor sensor signals
* Define anomaly and failure-event targets
* Establish leakage-safe temporal boundaries
* Build preprocessing and feature-engineering pipelines
* Establish baseline models
* Compare models using documented evaluation metrics
* Save and version verified model artifacts

### Technical Knowledge System

* Build a governed technical-document corpus
* Classify documents by source authority and equipment relevance
* Implement document extraction and chunking
* Generate and store embeddings
* Build vector and hybrid retrieval
* Add reranking and citation-grounded generation
* Evaluate retrieval and answer quality

### Application Engineering

* Develop prediction and retrieval APIs
* Add structured storage for predictions and system events
* Implement testing, logging, and monitoring
* Add Docker-based deployment
* Create a demonstration interface
* Document system limitations and operational requirements

## Next Engineering Milestone

Perform reproducible exploratory analysis over the verified MetroPT-3 Parquet dataset using DuckDB and Python.

The analysis must begin with signal distributions, operating-state frequencies, timestamp coverage, temporal-gap-aware segmentation, and representative sensor relationships before any target definition, feature engineering, or model training.

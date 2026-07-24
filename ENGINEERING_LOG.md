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
* Confirmed that the working tree and remote branch are synchronized

### Repository Protection

* Configured exclusions for Python caches and virtual environments
* Excluded environment-variable files, credentials, private keys, and certificates
* Excluded raw, interim, and processed datasets from Git
* Excluded generated outputs, local databases, model artifacts, logs, and analysis caches
* Verified representative ignore rules using `git check-ignore`
* Confirmed that no secret-related filenames are tracked by Git

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

## Repository Verification

| Item | Status |
| --- | --- |
| Local Git repository | Verified |
| Default branch | `main` |
| Remote name | `origin` |
| Remote tracking branch | `origin/main` |
| GitHub visibility | Public |
| Local-to-remote synchronization | Verified |
| Working tree | Clean after latest push |
| Secret-file exclusions | Verified |
| Dataset manifest | Implemented |
| Document manifest | Implemented |
| Manifest CSV structure | Validated |

## Current Engineering Workstream

The current workstream focuses on designing a reproducible MetroPT-3 data-ingestion process.

Active engineering tasks include:

* Defining the dataset download workflow
* Calculating and recording a file-integrity checksum
* Preserving the original dataset as immutable raw data
* Establishing ingestion configuration and validation rules
* Designing the raw-to-Parquet conversion process
* Preparing DuckDB-based analytical access
* Documenting failure handling and reproducibility requirements

## Planned Technical Milestones

### Data Engineering

* Implement reproducible MetroPT-3 download and integrity verification
* Preserve immutable raw data outside Git
* Validate the source schema and expected sensor fields
* Convert the raw CSV file to Parquet
* Query time-series data using DuckDB
* Create automated data-quality validation routines
* Record ingestion metadata and processing outcomes

### Machine Learning

* Perform exploratory analysis of compressor sensor signals
* Define anomaly and failure-event targets
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

## Architecture Decisions

### Real Industrial Data

The system uses MetroPT-3, a public industrial time-series dataset containing operational measurements from a metro-train Air Production Unit compressor.

### Data Provenance

Every dataset must be registered before ingestion. Source records include publisher information, source URL, access date, version, license, expected local filename, checksum, and processing status.

### Data Storage

The planned local analytical workflow uses Parquet and DuckDB. PostgreSQL is planned for application records, predictions, maintenance events, evaluation results, and vector storage.

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

## Verified Data-Quality Profiling

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

## Next Engineering Milestone

Convert the validated MetroPT-3 CSV to Parquet without modifying the immutable raw source, record reproducible processing metadata, and establish DuckDB-based local analytical access.

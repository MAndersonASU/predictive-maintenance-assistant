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
* Published the repository at:
  `MAndersonASU/predictive-maintenance-assistant`
* Created the initial project directory structure
* Added Python, environment, secret, data, and model-artifact exclusions through `.gitignore`
* Created the initial project README
* Verified the local-to-remote Git workflow
* Confirmed that the working tree and remote branch are synchronized

## Repository Verification

| Item                   | Status                          |
| ---------------------- | ------------------------------- |
| Local Git repository   | Verified                        |
| Default branch         | `main`                          |
| Remote name            | `origin`                        |
| Remote tracking branch | `origin/main`                   |
| GitHub visibility      | Public                          |
| Initial push           | Successful                      |
| Working tree           | Clean                           |
| Secret files excluded  | Configured through `.gitignore` |

## Current Engineering Workstream

The current workstream focuses on establishing a reproducible and professionally documented project foundation before beginning data ingestion and model development.

Active tasks include:

* Finalizing repository documentation
* Defining source-governance requirements
* Creating dataset and document manifests
* Establishing reproducible environment configuration
* Preparing the MetroPT-3 ingestion architecture
* Reviewing repository visibility and security settings

## Planned Technical Milestones

### Data Engineering

* Register the MetroPT-3 dataset in a structured source manifest
* Implement reproducible dataset download and integrity checks
* Preserve immutable raw data outside Git
* Convert raw CSV data to Parquet
* Query time-series data using DuckDB
* Create schema and data-quality validation routines

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

The system will use MetroPT-3, a public industrial time-series dataset containing operational measurements from a metro-train Air Production Unit compressor.

### Data Storage

The planned local analytical workflow uses Parquet and DuckDB. PostgreSQL is planned for application records, predictions, maintenance events, evaluation results, and vector storage.

### Document Governance

Technical documents will be classified as either:

* Exact dataset documentation
* Authoritative domain reference

Generic compressor documentation will not be represented as the exact equipment manual unless the equipment manufacturer and model are independently verified.

### Public Repository Policy

The public repository will contain:

* Source code
* Schemas
* Manifests
* Documentation
* Tests
* Small representative samples
* Reproducible setup instructions

It will not contain:

* API keys or credentials
* Local `.env` files
* Restricted documents
* Large generated artifacts
* Unverified performance claims
* Private development notes

## Next Engineering Milestone

Create professional source manifests for the MetroPT-3 dataset and technical-document corpus, followed by a reproducible data-ingestion design.

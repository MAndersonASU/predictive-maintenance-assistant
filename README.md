# Intelligent Predictive Maintenance and Technical Knowledge Assistant

A production-oriented AI engineering system for analyzing industrial sensor data, estimating equipment failure risk, and retrieving evidence-based maintenance information from technical documentation.

## Project Overview

This project combines machine learning, time-series analysis, data engineering, retrieval-augmented generation, and agent-based tool routing in a single predictive-maintenance platform.

The system is designed around the MetroPT-3 dataset, which contains real operational sensor measurements from a metro-train Air Production Unit compressor. The project will use these measurements to identify abnormal operating behavior and support failure-risk analysis.

## System Objectives

* Process and validate real industrial time-series data
* Analyze compressor pressure, temperature, motor-current, and control signals
* Develop and compare anomaly-detection and failure-prediction models
* Store processed data, predictions, and maintenance events
* Retrieve relevant information from authoritative technical documents
* Generate evidence-based responses with source citations
* Route requests between machine-learning models, databases, and retrieval tools
* Provide reproducible evaluation, monitoring, and deployment workflows

## Planned Architecture

```text
MetroPT-3 Sensor Data
        ↓
Data Validation and Processing
        ↓
Feature Engineering
        ↓
Predictive Maintenance Models
        ↓
Prediction and Anomaly Database
        ↓
API and Monitoring Services
        ↓
Technical Knowledge Assistant

Technical Documents
        ↓
Document Processing and Chunking
        ↓
Embeddings and Vector Search
        ↓
Retrieval-Augmented Generation
        ↓
Evidence-Based Maintenance Responses
```

## Current Project Status

The repository foundation has been established with:

* Version control using Git and GitHub
* A structured project directory
* Environment and secret-management rules
* Initial project documentation
* An isolated development environment
* A reproducible source-control workflow

The next implementation milestone focuses on data-source governance, MetroPT-3 ingestion, schema validation, and exploratory analysis.

## Technology Roadmap

The expected technology stack includes:

* Python
* pandas and NumPy
* scikit-learn
* DuckDB and Parquet
* PostgreSQL and pgvector
* OpenAI APIs
* FastAPI
* Docker
* Automated tests and evaluation pipelines

Technology selections may be refined as system requirements and benchmark results become available.

## Data and Documentation

The project uses real public industrial data and authoritative technical references.

Source information, licensing, document classification, version details, and equipment-match status will be maintained through structured data and document manifests.

Large raw datasets, private configuration files, API keys, generated model artifacts, and restricted technical documents will not be committed directly to the public repository.

## Project Principles

* Reproducible data processing
* Honest and measurable model evaluation
* Clear separation between verified capabilities and planned work
* Secure handling of credentials and sensitive configuration
* Traceable technical sources and model outputs
* Production-oriented testing, monitoring, and documentation

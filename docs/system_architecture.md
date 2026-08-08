# Integrated System Architecture

## Status

This document describes the current implemented architecture. Planned application, persistence, monitoring, container, and demonstration layers are identified separately and are not represented as completed capabilities.

## Governed Data and Machine-Learning Path

```text
UCI MetroPT-3 source
    |
    v
Acquisition + SHA-256 identity
    |
    v
Schema / data-quality validation
    |
    v
Parquet + DuckDB analytical layer
    |
    v
Gap-aware event governance and target states
    |
    v
Causal, segment-bounded feature engineering
    |
    +-------------------------------+
    |                               |
    v                               v
Transparent robust-distance     Bounded Isolation Forest
benchmark                       candidate comparison
    |                               |
    v                               v
Frozen baseline evidence        Validation-selected frozen model
    |                               |
    +---------------+---------------+
                    |
                    v
            One-time held-out reporting
```

The machine-learning release uses chronological partitions and a frozen 48-feature set. Unverified rows are not converted into a verified healthy class. Alarm burden is operational review load, not a false-positive rate, and unusualness is not a failure probability.

## Governed Technical-Knowledge Path

```text
Governed technical sources
    |
    v
Source identity / license / scope / equipment relevance
    |
    v
Completeness checks
    |
    v
Deterministic extraction + normalization
    |
    v
354 provenance-preserving chunks
    |
    +------------------------------+
    |                              |
    v                              v
TF-IDF keyword retrieval        128-dim LSA retrieval
    |                              |
    +--------------+---------------+
                   |
                   v
          Bounded hybrid fusion
                   |
                   v
          Deterministic reranking
                   |
                   v
          Bounded evidence assembly
                   |
                   v
          Stable source citations
                   |
          +--------+---------+
          |                  |
          v                  v
Grounded answer      Insufficient-evidence refusal
```

Source identity, classification, checksums, locators, and scope notes survive the complete retrieval-to-answer path. General compressed-air guidance is never relabeled as exact MetroPT equipment instruction.

## Current Integration Boundary

The data/ML and technical-knowledge subsystems are independently implemented and verified. The repository has not yet claimed completion of the application integration layer.

The next governed milestone evaluates retrieval and grounded-answer quality before API integration.

## Planned Application and Operations Layers

The following remain planned and must be verified before being described as implemented:

```text
Prediction / retrieval / grounded-answer APIs
    -> bounded local persistence
    -> structured logging and monitoring controls
    -> configuration and secret handling
    -> Docker reproducibility
    -> professional demonstration interface
    -> end-to-end integration and release validation
```

## Evidence Boundaries

- Held-out model evidence cannot be used to retune the frozen model.
- Retrieval smoke checks are implementation checks, not formal retrieval-quality claims.
- Grounding smoke checks are implementation checks, not formal faithfulness or usefulness claims.
- Exact-equipment instructions require governed exact-equipment documentation.
- Generated evidence and large runtime artifacts remain outside Git.

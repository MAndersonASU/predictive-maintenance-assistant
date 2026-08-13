# Integrated System Architecture

## Status

This document describes the implemented bounded local release. The frozen machine-learning and governed knowledge artifacts remain read-only inputs to the API and demonstration layers.

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

## Implemented Application and Demonstration Path

The two governed subsystems are connected through one loopback-only FastAPI application. The browser interface does not duplicate prediction or knowledge logic; it calls the same tested contracts used by other local clients.

```text
Local browser at 127.0.0.1:8000
    |
    +--> prediction workspace --> GET schema --> POST predict --> frozen model
    |
    +--> knowledge workspace  --> POST retrieve + POST answer
    |                                  |              |
    |                                  v              v
    |                              evidence      cited answer/refusal
    |
    +--> operations workspace --> readiness + counters + bounded review records
                                      |
                                      v
                            bounded SQLite application state
```

The interface is served from committed self-contained HTML, CSS, and JavaScript assets. It uses no CDN, remote font, analytics service, external inference service, or client-side persistence. Fixed asset routing prevents arbitrary filesystem access. A restrictive content-security policy permits connections only to the same local origin.

FastAPI provides strict request models, sanitized error responses, request IDs, OpenAPI documentation, and liveness/readiness endpoints. SQLite stores bounded local summaries while excluding raw feature values by default. Docker reproduces the runtime with an unprivileged user, a read-only root filesystem, loopback-only host publication, read-only governed artifact mounts, and a Docker-managed writable state volume.

## Release Boundary

The current implementation is a functionally integrated **bounded local demonstration release**. It is not a public production deployment. Authentication is intentionally disabled under the loopback-only constraint. Public hosting would require separately implemented authentication, authorization, TLS, rate limiting, secret management, durable production persistence, network policy, and operational support controls.

## Evidence Boundaries

- Held-out model evidence cannot be used to retune the frozen model.
- Retrieval smoke checks are implementation checks, not formal retrieval-quality claims.
- Grounding smoke checks are implementation checks, not formal faithfulness or usefulness claims.
- Exact-equipment instructions require governed exact-equipment documentation.
- Generated evidence and large runtime artifacts remain outside Git.
- The demonstration interface does not rebuild, refit, retune, or reevaluate governed artifacts.
- Local interaction counters and human-review records are demonstration evidence, not benchmark evidence.

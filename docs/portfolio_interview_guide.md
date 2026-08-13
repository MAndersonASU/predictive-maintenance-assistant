# Portfolio and Interview Guide

## One-sentence project description

Built a governed predictive-maintenance and technical-knowledge assistant that connects industrial time-series anomaly detection, provenance-preserving hybrid retrieval, citation-grounded answers, tested APIs, bounded persistence, Docker execution, and a professional local interface.

## Résumé bullet options

- Engineered an end-to-end predictive-maintenance system for 1.52 million MetroPT-3 compressor observations, with reproducible acquisition, gap-aware time-series processing, causal feature engineering, frozen model evaluation, and **365 automated regression tests**.
- Built a governed technical-knowledge pipeline across three sources and 354 deterministic chunks using TF-IDF, 128-dimensional LSA, bounded hybrid retrieval, deterministic reranking, stable citations, and explicit insufficient-evidence refusal.
- Delivered a loopback-only FastAPI and Docker demonstration integrating a frozen 48-feature Isolation Forest, retrieval, citation-grounded answers, readiness, metrics, and privacy-bounded SQLite history without duplicating model or retrieval logic.
- Applied production-minded controls including chronological leakage prevention, checksum-verified artifacts, pinned dependencies, unprivileged containers, read-only artifact mounts, structured events, sanitized failures, and CI verification.

## LinkedIn project summary

I built an Intelligent Predictive Maintenance and Technical Knowledge Assistant that combines my mechanical-engineering background with AI engineering. The project analyzes governed MetroPT-3 compressor data, scores unusual operating observations with a frozen anomaly-detection model, retrieves evidence from a controlled technical corpus, and produces citation-grounded answers or a clear refusal when the evidence is insufficient. I also built the tested API, local persistence, monitoring controls, hardened Docker path, and self-contained browser demonstration. The strongest part of the work is the evidence discipline: chronological leakage controls, frozen held-out evaluation, artifact checksums, source provenance, visible limitations, and no unsupported production or business claims.

## Interview explanation: architecture

The system has two governed paths. The data path validates and transforms MetroPT-3 observations, materializes chronological targets and causal features, and compares a transparent robust-distance benchmark with a frozen Isolation Forest. The knowledge path governs three technical sources, creates provenance-preserving chunks, combines keyword and LSA retrieval, reranks evidence, and assembles cited answers. One FastAPI application exposes both paths to the same local browser interface and persists only bounded summaries.

## Interview explanation: why Isolation Forest

The dataset does not provide a reliable verified healthy class, so conventional supervised classification claims would be misleading. Isolation Forest provides an anomaly score without pretending that unusualness is failure probability. A transparent robust-distance detector remains the benchmark. Candidate selection used validation only, and the selected model and threshold were frozen before one-time held-out reporting.

## Interview explanation: why hybrid retrieval

Keyword retrieval is strong for exact technical terms, while LSA can recover related wording. Bounded fusion combines both signals, and deterministic reranking makes the final evidence order reproducible. Source classification and locators survive the full path so a general compressed-air guide cannot be presented as an exact equipment manual.

## Interview explanation: a failure and correction

During integration, Windows regression testing exposed SQLite file-handle retention, and clean Docker rebuilding exposed transitive dependency drift. Both were treated as engineering defects: the connections were explicitly closed, the container dependency closure was pinned, regression coverage was added, and the complete suite was rerun before commit. This shows why cross-platform and clean-state verification matter even when focused tests already pass.

## Interview explanation: limitations

The project is a bounded local demonstration, not a public production or safety system. It has no verified healthy negative class, only one governed event in the held-out advanced-model test population, three preserved UCI-specific retrieval misses, and no exact MetroPT equipment manual. Public deployment and equipment-specific instructions therefore remain outside the supported claims.

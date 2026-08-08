# Governed Knowledge Retrieval Method

## Purpose

This module adds the first retrieval layer over the already-governed technical-document chunks. It consumes the existing `data/interim/knowledge/chunks.jsonl` artifact and does not reacquire, re-extract, rechunk, rerank, or generate answers.

## Frozen Retrieval Contract

The retrieval configuration is declared in `config/knowledge_retrieval.json` before evaluation. The governed input is fixed to the verified 354-chunk corpus with SHA-256 `4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d`.

The retrieval path has three components:

1. **Keyword representation:** scikit-learn TF-IDF with one- and two-word features, L2 normalization, sublinear term frequency, and a vocabulary cap of 16,000 features.
2. **Vector embedding:** deterministic latent semantic analysis (LSA) created by applying 128-component `TruncatedSVD` to the governed TF-IDF document matrix with `random_state=42` and seven randomized-SVD iterations, followed by L2 normalization.
3. **Hybrid fusion:** vector cosine similarity receives weight 0.65 and keyword cosine similarity receives weight 0.35. Candidate generation is bounded to the union of the best 30 vector and keyword candidates. Returned `top_k` is bounded to at most 12; the default is 8.

These parameters are implementation controls, not retrieval-quality claims. Retrieval quality is evaluated separately under a governed evaluation milestone.

## Why LSA Embeddings Are Used Here

The project already pins scikit-learn and has only 354 governed chunks. A local LSA embedding creates a reproducible dense semantic vector space without introducing a remote model download, model-cache lifecycle, GPU dependency, or additional supply-chain surface before retrieval quality has been measured. A neural embedding model remains an evidence-driven future option if evaluation demonstrates that the bounded local representation is inadequate.

## Reproducibility and Stale-Evidence Protection

Index construction refuses to proceed unless both the governed chunk count and the exact chunk-file SHA-256 match the frozen governed corpus evidence. The generated report records the retrieval configuration fingerprint, keyword vocabulary signature, SVD-component signature, dense document-embedding signature, runtime versions, and combined deterministic index signature.

A saved index is rejected if the current configuration or chunk corpus differs from the versions used to build it. Generated retrieval artifacts remain under ignored `data/interim/` and `outputs/` paths.

## Provenance Preservation

Every retrieval result preserves all available source and locator fields from the governed chunk, including source ID and title, publisher, URL and DOI, source classification, equipment-relevance boundary, license or usage status, retrieval identity, scope note, source checksum, chunk checksum, locator, ordering fields, word count, and chunk text.

The result adds only retrieval rank and the keyword, vector, and hybrid scores. It does not rewrite source metadata.

## Scope Boundary

The current retrieval layer implements retrieval only. It intentionally does **not** implement:

- reranking;
- evidence assembly for an answer;
- citation rendering;
- answer generation;
- insufficient-evidence refusal behavior;
- retrieval-quality or answer-quality claims.

Those functions belong to later governed milestones so retrieval behavior can be evaluated independently.

## Runtime Commands

Build the governed index and report:

```powershell
python -m predictive_maintenance.knowledge.retrieval --config config/knowledge_retrieval.json build
```

Run a bounded query after a successful build:

```powershell
python -m predictive_maintenance.knowledge.retrieval --config config/knowledge_retrieval.json query "compressor pressure maintenance" --top-k 5
```

Run the focused controlled tests:

```powershell
python -m pytest -q tests/test_knowledge_retrieval.py
```

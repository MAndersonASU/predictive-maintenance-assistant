# Governed Knowledge Retrieval Method

> **Record status:** Implemented retrieval-subsystem specification. Downstream deterministic reranking, citation assembly, and insufficient-evidence behavior are implemented in `knowledge_grounding.py`; this file intentionally describes retrieval only.

## Purpose

This module adds the retrieval layer over governed technical-document chunks. It consumes `data/interim/knowledge/chunks.jsonl` and does not reacquire, re-extract, rechunk, rerank, or generate answers.

## Frozen Retrieval Contract

The retrieval configuration is declared in `config/knowledge_retrieval.json`. The governed input is fixed to the verified 354-chunk corpus with SHA-256 `4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d`.

The retrieval path has three components:

1. **Keyword representation:** scikit-learn TF-IDF with one- and two-word features, L2 normalization, sublinear term frequency, and a 16,000-feature vocabulary cap.
2. **Vector embedding:** deterministic latent semantic analysis using 128-component `TruncatedSVD`, `random_state=42`, seven randomized-SVD iterations, and L2 normalization.
3. **Hybrid fusion:** vector cosine similarity weight 0.65 and keyword cosine similarity weight 0.35. Candidate generation is bounded to the union of the best 30 vector and keyword candidates. Returned `top_k` is at most 12; default is 8.

These parameters are implementation controls, not retrieval-quality claims.

## Why LSA Embeddings Are Used Here

The corpus contains only 354 governed chunks and the project already pins scikit-learn. Local LSA creates a reproducible dense semantic space without remote model downloads, GPU dependencies, model-cache lifecycle, or additional supply-chain surface before retrieval quality is measured.

## Reproducibility and Stale-Evidence Protection

Index construction refuses to proceed unless governed chunk count and exact chunk-file SHA-256 match the frozen corpus evidence. Saved indexes are rejected when the configuration or corpus identity differs from index construction.

## Provenance Preservation

Every result preserves source ID/title, publisher, URL/DOI, classification, equipment relevance, usage status, retrieval identity, scope note, source checksum, locator, ordering fields, word count, chunk checksum, and text.

The retrieval result adds only retrieval rank and keyword/vector/hybrid scores.

## Retrieval-Subsystem Boundary

This module deliberately does not rerank, assemble answer evidence, render citations, generate answers, or decide insufficient-evidence responses. Those responsibilities belong to the separately implemented grounding layer. Retrieval quality and answer quality remain separate evaluation concerns.

## Runtime Commands

```powershell
python -m predictive_maintenance.knowledge.retrieval --config config/knowledge_retrieval.json build
python -m predictive_maintenance.knowledge.retrieval --config config/knowledge_retrieval.json query "compressor pressure maintenance" --top-k 5
python -m pytest -q tests/test_knowledge_retrieval.py
```

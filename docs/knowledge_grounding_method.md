# Governed Reranking and Citation-Grounded Answer Assembly

## Purpose

This component extends the existing governed hybrid retrieval layer with deterministic reranking, bounded evidence assembly, stable citation identifiers, and explicit insufficient-evidence behavior. It does not modify the frozen technical-knowledge corpus or rebuild the hybrid retrieval index.

## Inputs and boundaries

The implementation consumes results from `predictive_maintenance.knowledge.retrieval.retrieve()`. Those results already preserve source identity, classification, checksums, locators, and chunk text. The grounding stage treats those provenance fields as immutable evidence metadata.

The current corpus contains exact dataset sources for MetroPT-related dataset context and an authoritative general compressed-air reference. It does **not** contain a verified exact MetroPT equipment service manual. Equipment-specific service instructions must therefore be refused unless a future governed source is explicitly classified as `exact_equipment_source`.

## Deterministic reranking

Each bounded hybrid candidate receives a rerank score composed of four normalized terms: the existing hybrid retrieval score, query-token coverage, adjacent query-phrase overlap, and a small classification-affinity term based on query scope. The weights are fixed in `config/knowledge_grounding.json`. Ties are resolved deterministically by hybrid score and chunk identifier. Original retrieval rank remains visible beside rerank rank.

No external model, remote API, hidden service, or newly downloaded model is required.

## Evidence scope

The module uses deterministic query-scope detection only to enforce source boundaries. Dataset-specific queries favor exact dataset sources; general compressed-air questions favor authoritative general references; equipment-specific questions require an `exact_equipment_source`. Classification affinity can affect rank, but never changes a source's stored classification.

## Citation-grounded answer assembly

Evidence is bounded by a minimum rerank score and maximum evidence-chunk count. Selected sentences are chosen by deterministic query-token overlap and returned with stable citation IDs such as `[S1]`. Citation records preserve chunk ID, source ID/title, publisher, URL, DOI when present, classification, equipment relevance, scope note, locator, source checksum, and chunk-text checksum.

Answers explicitly identify whether their evidence is governed dataset evidence, authoritative general guidance, or verified equipment evidence.

## Insufficient-evidence behavior

The module returns `status="insufficient_evidence"` instead of inventing an answer when no candidate survives the threshold, no supported sentence can be assembled, or an equipment-specific request lacks exact equipment evidence. General or dataset citations may still be exposed as context while being explicitly identified as not verified exact-equipment instructions.

## Validation scope

The `validate` command runs three bounded implementation smoke cases: a MetroPT dataset-context question expected to answer, a general compressed-air maintenance question expected to answer, and a manufacturer-specific MetroPT compressor question expected to refuse.

`outputs/knowledge_grounding_report.json` is implementation evidence only. It does not constitute formal retrieval-quality, citation-correctness, faithfulness, or answer-usefulness evaluation; that requires the separately governed RAG evaluation milestone.

## Commands

```powershell
python -m predictive_maintenance.knowledge.grounding validate
python -m predictive_maintenance.knowledge.grounding query "What general compressed-air maintenance guidance addresses leaks and pressure losses?"
python -m pytest .\tests\test_knowledge_grounding.py -q
```

The generated report remains under `outputs/` and must stay excluded from Git.

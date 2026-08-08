# Governed Technical-Knowledge Corpus and Chunking Method

## Purpose

This module creates the bounded technical-document foundation used by later retrieval and citation-grounded answering. It intentionally separates source governance from retrieval. No document is embedded or treated as evidence until its identity, publisher, usage status, relevance, local state, and provenance are recorded.

## Governed corpus

The first corpus contains three deliberately different evidence roles:

1. **MetroPT-3 UCI data description** — exact dataset documentation associated with UCI dataset 791 and DOI `10.24432/C5VW3R`. The PDF is expected to already exist at `data/raw/Data Description_Metro.pdf` from the governed dataset acquisition workflow.
2. **Scientific Data MetroPT article** — authoritative MetroPT project/dataset literature, DOI `10.1038/s41597-022-01877-3`, retained under its stated CC BY 4.0 terms. The paper describes a 2022 MetroPT collection, so the corpus records an explicit scope note and does not assume it is identical to the UCI MetroPT-3 2020 dataset. It is dataset/project evidence and is not a manufacturer equipment manual.
3. **U.S. Department of Energy compressed-air sourcebook** — authoritative general compressed-air guidance. It is explicitly classified as a general reference and must never be presented as the exact MetroPT equipment manual.

The committed source metadata lives in `config/knowledge_corpus.json`. Downloaded documents, normalized text, chunks, and runtime reports stay in ignored locations.

## Deterministic extraction

PDF text is extracted page by page with `pypdf`. Each non-empty page becomes an extraction unit with a stable `page:N` locator. HTML uses Python's standard `HTMLParser`; script, style, noscript, and SVG content is excluded before normalization. UTF-8 text is also supported for controlled tests and future governed text sources.

No OCR is performed. A PDF with no extractable text fails with an actionable error instead of silently invoking a nondeterministic or ungoverned OCR path.

## Normalization

Normalization is deliberately conservative:

- Unicode is normalized with NFKC.
- HTML character entities and non-breaking spaces are normalized.
- CRLF/CR line endings become LF.
- repeated horizontal whitespace is collapsed;
- paragraph boundaries are preserved;
- no semantic rewriting, summarization, translation, or model-generated cleanup is performed.

## Chunking contract

Chunking is word-bounded and deterministic. The initial contract is:

- maximum: **220 words** per chunk;
- overlap: **40 words**;
- minimum preferred tail: **20 words**;
- chunks never cross extraction-unit boundaries, so PDF page provenance is preserved;
- chunk identifiers include source ID, unit index, unit-local chunk index, and the first 12 hexadecimal characters of the chunk-text SHA-256.

The overlap exists to reduce loss of context near chunk boundaries. The final small tail may be merged into the previous chunk when the merge stays under the maximum size.

## Provenance record

Every chunk carries:

- source and chunk identifiers;
- title and publisher;
- source URL and DOI when available;
- exact-dataset/general-reference classification;
- equipment-relevance boundary;
- license or usage status;
- retrieval identity;
- explicit scope note, including dataset-edition boundaries;
- source-file SHA-256;
- page/document locator;
- chunk ordering fields;
- word count;
- chunk-text SHA-256;
- normalized chunk text.

The workflow rejects duplicate chunk IDs, invalid classifications, broken text checksums, invalid source checksums, and word-count inconsistencies.

## Generated evidence

A successful run writes:

- `data/interim/knowledge/normalized/<source_id>.txt`
- `data/interim/knowledge/chunks.jsonl`
- `outputs/knowledge_corpus_report.json`

All three locations are already covered by the repository's governed ignore rules. The report deliberately contains no runtime timestamp, so identical source bytes and identical configuration produce identical normalized and chunk output bytes.

## Safety and interpretation boundary

Source authority does not make a general compressed-air publication an exact equipment manual. Later retrieval and answer-generation stages must preserve the `classification` and `equipment_relevance` fields and must surface that distinction in evidence and citations.

The corpus does not claim that every statement in a source applies to the MetroPT train compressor. It preserves the source so later retrieval can distinguish dataset-specific evidence from general authoritative guidance.

## Reproducible command

From repository root in the activated virtual environment:

```powershell
$env:PYTHONPATH = "src"
python -m predictive_maintenance.knowledge.corpus
```

For an already materialized corpus with network access prohibited:

```powershell
$env:PYTHONPATH = "src"
python -m predictive_maintenance.knowledge.corpus --offline
```

The second command succeeds only when all remote documents already exist locally.

## Source-content completeness gate

Every governed source declares a conservative `minimum_extracted_words` threshold and one or more `required_text_markers`. Extraction must satisfy both controls before normalization or chunking can continue. This prevents consent pages, anti-bot responses, redirects, short landing pages, or other incomplete retrievals from being silently accepted as technical evidence.

The Scientific Data article is retrieved from its PubMed Central archival full-text record (`PMCID PMC9747912`) while preserving the Scientific Data publisher identity and DOI `10.1038/s41597-022-01877-3`. This is a retrieval-location choice, not a change to the cited publication. The source remains explicitly scoped as the related 2022 MetroPT collection and is not treated as byte-, schema-, or period-identical to the 2020 UCI MetroPT-3 corpus used by this project.

## Failed-run evidence invalidation

Before a governed corpus refresh starts, previously generated knowledge-corpus report, chunk, and normalized-text outputs are removed. Raw governed source files are not removed. If source materialization, extraction, completeness validation, provenance validation, or chunk generation fails, no older successful report or chunk file remains available to be mistaken for evidence from the failed run.

The UCI `Data Description_Metro.pdf` is an already-governed archive member. Its completeness check combines a minimum extracted-word threshold with the stable `MetroPT` identity marker; it intentionally avoids depending on prose such as `Air Production Unit`, because PDF text extraction can omit or fragment narrative phrases even when the underlying document is valid.

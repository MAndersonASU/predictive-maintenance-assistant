# Governed Retrieval and Grounded-Answer Evaluation

## Purpose

This evaluation measures the existing technical-knowledge workflow without
changing the governed corpus, retrieval index, reranking parameters, grounding
thresholds, or source-classification boundaries.

The evaluation is deliberately diagnostic. Retrieval quality, citation
correctness, faithfulness, answer usefulness, failure cases, and limitations
are reported separately so one strong dimension cannot hide weakness in
another.

## Frozen inputs

The evaluator requires the existing governed artifacts to match the identities
recorded in `config/knowledge_evaluation.json`.

The frozen inputs include:

- corpus ID `predictive_maintenance_technical_knowledge_v1`;
- 354-chunk corpus SHA-256
  `4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d`;
- retrieval ID `predictive_maintenance_hybrid_retrieval_v1`;
- retrieval-index SHA-256
  `2700dac28adfc9a80a9bd28c3af177237d45e845ef94c37cd4e68b421d4442b7`;
- grounding ID `predictive_maintenance_grounded_answers_v1`.

An identity mismatch stops evaluation. The evaluator never rebuilds or retunes
those artifacts.

## Governed evaluation set

The initial evaluation set contains twelve cases:

- four MetroPT/dataset-context cases;
- four authoritative general compressed-air guidance cases;
- four exact-equipment requests that must be refused because no governed exact
  MetroPT equipment manual is present.

Answerable cases carry source-level relevance labels, expected source
classification, expected answer behavior, and small concept groups used for a
deterministic usefulness proxy. Equipment-boundary cases intentionally contain
no relevant exact-equipment source label.

## Retrieval quality

Retrieval is evaluated before reranking/answer assembly using source-level
labels.

Reported retrieval metrics include:

- source Hit@1, Hit@3, and Hit@5;
- mean reciprocal rank of the first labeled relevant source;
- top-1 expected source-classification rate;
- exact-equipment boundary retrieval checks for refusal cases.

These are source-level retrieval metrics, not exhaustive chunk-level recall.

## Citation correctness

Citation correctness is structural and provenance-based.

For every emitted citation, the evaluator verifies that its chunk ID maps back
to a reranked evidence record and that source ID, source classification,
locator, and text checksum match exactly. It also verifies that answer citation
markers correspond to the emitted citation records and separately records
whether answerable-case citations stay inside the expected source
classification.

For answered cases, inline answer markers must map exactly to emitted citation
records. An insufficient-evidence refusal may still expose traceable retrieved
source metadata as context. Because those sources are not being cited as
support for an unavailable equipment-specific answer, inline marker coverage is
not scored for refusal text; provenance traceability is still checked.

This does not claim that every possible citation is ideal. It verifies that the
citations emitted by the implemented pipeline are traceable and scope-aligned
under the governed case labels.

## Faithfulness

The current answer assembler is extractive: selected evidence sentences are
copied into the answer and followed by stable citation markers.

Faithfulness therefore checks whether each marked answer claim appears in the
text of the cited reranked chunk. Equipment-specific cases are evaluated
separately for the required `no_exact_equipment_evidence` refusal behavior.

A high extractive-support rate should not be generalized to free-form
generative RAG systems.

## Answer usefulness

Usefulness is kept separate from faithfulness.

For answerable cases, the evaluator verifies expected status, reason code,
intent, and deterministic coverage of small case-specific concept groups. For
equipment-boundary cases, usefulness means returning the expected safe refusal
with the correct reason and intent.

Concept coverage is a reproducible proxy, not a human preference score.

## Failure cases

The report retains per-case failure flags instead of hiding them behind one
overall pass/fail label. Examples include:

- relevant-source miss at the largest governed cutoff;
- top-1 source-classification mismatch;
- citation traceability failure;
- citation marker mismatch;
- citation source-scope misalignment;
- unsupported cited claim;
- incorrect exact-equipment refusal;
- unexpected status, reason, or intent;
- low usefulness concept coverage.

The report status is `completed` when the evaluation executes successfully.
Low quality remains visible as measured evidence and does not trigger automatic
retuning.

## Generated evidence

The evaluator writes:

```text
outputs/knowledge_evaluation_report.json
```

The output is generated evidence and remains excluded from Git under the
existing `outputs/*` ignore rule. A stale report is removed before a new run,
and a failed run does not leave a previous successful report that could be
mistaken for current evidence.

## Reproducibility command

From the repository root with the project virtual environment active and
`PYTHONPATH=src`:

```text
python -m predictive_maintenance.knowledge.evaluation evaluate --config config/knowledge_evaluation.json
```

The evaluation uses no external LLM judge, remote inference service, secret, or
network-dependent evaluator.

## Interpretation limits

The evaluation set is intentionally small and bounded. Relevance labels are
source-level. Usefulness is a deterministic proxy. No exact-equipment manual is
present. Results apply only to the current three-source corpus, frozen hybrid
index, deterministic reranker, and extractive citation-grounded answer
assembler. They do not establish production safety, broad factual coverage,
business impact, or general RAG quality.

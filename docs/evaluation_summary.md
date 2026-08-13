# Release Evaluation Summary

## Scope

The release contains two separately governed evaluation tracks: machine-learning anomaly detection and citation-grounded technical knowledge. Their metrics answer different questions and must not be combined into a single quality score.

## Machine-learning evidence

The transparent robust-distance detector was finalized before advanced-model development. Eight Isolation Forest configurations were compared under a predeclared training/validation protocol. Candidate `iforest_ne200_ms4096_mf1p0`, its 48 features, and threshold `0.601902290159477` were frozen before the one authorized held-out evaluation.

| Governed held-out measure | Isolation Forest | Robust-distance baseline |
|---|---:|---:|
| Documented-event coverage | 1.000 | 1.000 |
| Mean first-alarm latency for covered events (seconds) | 218.000 | 15,804.000 |
| Alarms per 24 observed hours | 69.863 | 94.192 |

These are operational measures. The data does not support accuracy, precision, recall, false-positive rate, calibrated failure probability, or verified healthy-class claims. No held-out result was used for refitting, threshold changes, feature changes, or candidate reselection.

## Retrieval and grounded-answer evidence

The fixed evaluation contains twelve governed cases and uses the frozen 354-chunk corpus, hybrid index, reranker, evidence assembler, and refusal behavior.

| Measure | Verified result |
|---|---:|
| Source Hit@1 / Hit@3 / Hit@5 | 0.625 |
| Mean reciprocal rank | 0.645833 |
| Top-1 expected source classification | 1.000 |
| Traceable citations | 40 / 40 |
| Cited claims supported | 40 / 40 |
| Answered-case citation-marker coverage | 1.000 |
| Source-scope alignment | 1.000 |
| Exact-equipment refusal boundary | 1.000 |
| Answer-usefulness proxy pass | 1.000 |
| Mean answerable-case concept coverage | 0.9375 |

Three UCI-specific cases remain `retrieval_source_miss_at_5`. They are preserved as measured limitations and were not used to retune the corpus, retrieval parameters, reranking, or grounding.

## Integration evidence

The release verifies one loopback-only application path for prediction, retrieval, citation-grounded answers, readiness, metrics, bounded persistence, and the self-contained browser interface. Docker checks cover pinned dependencies, an unprivileged runtime, read-only governed artifact mounts, dropped capabilities, `no-new-privileges`, and host publication limited to `127.0.0.1:8000`.

The final verified repository suite contains **365 passing tests**. Exact release verification is recorded in the engineering log and GitHub Actions, and no held-out evaluator is part of routine regression verification.

## Supported conclusion

The evidence supports a reproducible, functionally integrated bounded local portfolio release. It does not establish public production readiness, broad factual coverage, safety certification, reliability improvement, financial impact, or equipment-specific maintenance authority.

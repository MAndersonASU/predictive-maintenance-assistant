# Governed Advanced-Model Comparison Contract

> **Record status:** Implemented historical contract. The bounded Isolation Forest validation and the separately governed one-time held-out evaluation were subsequently completed under these frozen comparison rules.

## Purpose

This method defines comparison rules fixed before the advanced anomaly model is fitted. It preserves the finalized robust-distance baseline as a transparent reference, blocks test-driven design, bounds the candidate search, and records a deterministic validation-selection rule.

## Finalized baseline boundary

The robust-distance baseline is frozen at commit `1b03c4ae695e04da1f03304f7154b35f1da92d1a`. Its 48 retained features, 0.995 threshold quantile, and threshold `7857.013759410036` cannot be revised from advanced-model evidence.

Baseline held-out results are prohibited from candidate design, feature selection, preprocessing decisions, hyperparameter selection, threshold selection, or validation ranking.

## Governed population

- Fit population: eligible training-reference rows.
- Validation scoring: eligible validation rows.
- Known-event evidence: eligible documented-event validation rows.
- Alarm-burden evidence: eligible unlabeled validation rows.
- Held-out partition: locked during contract validation and model selection.

Unverified operational rows remain unlabeled. They are not converted into verified healthy negatives.

## Bounded candidate family

The only authorized family is `sklearn.ensemble.IsolationForest`.

| Parameter | Allowed values |
|---|---|
| `n_estimators` | 100, 200 |
| `max_samples` | 1024, 4096 |
| `max_features` | 0.5, 1.0 |

Fixed parameters are `contamination="auto"`, `bootstrap=False`, `random_state=42`, and `n_jobs=-1`. The Cartesian product contains exactly eight candidates.

## Score and threshold

Candidate unusualness is `-score_samples`; larger values mean more unusual behavior. Each candidate threshold is the 0.995 quantile of eligible training-reference scores and is frozen before validation. The score is not a failure probability.

## Deterministic validation selection

Candidates are ranked lexicographically:

1. maximize documented-event coverage;
2. minimize mean first-alarm latency among covered events;
3. minimize alarms per 24 observed hours;
4. minimize deterministic candidate-complexity rank.

Alarm burden is not a false-positive rate. Unsupported conventional classification metrics remain prohibited.

## Held-out access control

At the comparison-contract stage, held-out access was prohibited until the contract, candidate implementation, validation run, selected candidate, frozen threshold, validation-decision checksum, and separate explicit authorization were all verified.

That authorization was later recorded and the frozen selected model was evaluated once. The held-out result did not change this comparison contract.

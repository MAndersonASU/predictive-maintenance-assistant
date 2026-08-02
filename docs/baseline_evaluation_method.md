# MetroPT-3 Baseline and Temporal-Evaluation Contract

## Purpose

This contract defines who may be used to establish a future transparent anomaly baseline, how later observations may be scored, and which evaluation statements the available evidence can support. The validation workflow materializes row-level eligibility evidence only. It does not fit preprocessing, train a model, calculate anomaly scores, generate alarms, or report performance.

## Target interpretation

The dataset contains documented failure intervals but no verified healthy-negative class. A row with `target_state = unverified` is therefore an unlabeled operational observation, not a confirmed normal or negative example. Documented-failure rows are verified positives for event-oriented evaluation. Pre-event exclusions, chronological partition buffers, incomplete 30-row histories, and rows with any exclusion reason are ineligible.

The future reference population is restricted to eligible `unverified` rows in the training partition. It represents the observed training-period operating mixture. Contamination by unrecorded abnormal behavior remains possible and must be stated as a limitation.

## Transparent baseline

The selected baseline is a training-reference robust-distance method. A later implementation may fit each numeric model feature's median and interquartile range on eligible training-reference rows only. Features with zero interquartile range must be excluded with a recorded reason. The same frozen parameters must then be applied unchanged to validation and test rows.

The planned score is the maximum absolute robust z-score across retained features. It is an unusualness score relative to the unlabeled training reference, not a probability of failure. A candidate alarm threshold may use the 99.5th percentile of eligible training-reference scores. The threshold must be frozen before validation begins, and the test partition must remain locked until the complete method is frozen.

## Temporal and segment controls

Training precedes validation, and validation precedes test. Random splitting is prohibited. Eligible rows require the complete causal 30-row history already produced inside a single segment and partition. No preprocessing parameter, feature history, threshold choice, or evaluation relationship may cross backward from a later partition.

## Supported evaluation language

Documented events can support event coverage, first-alarm latency, and alarm contiguity within the recorded event interval. Unlabeled operating periods can support alarm burden, alarms per 24 observed hours, and score-distribution drift. Alarm burden describes operational review load; it is not a false-positive rate because the absence of a documented event does not verify a healthy negative.

Accuracy, precision, specificity, false-positive rate, and ROC AUC are unsupported under the current labels. Standard row-level recall is also not the primary measure because long events would dominate the count; documented-event coverage is reported at the event level instead.

## Validation evidence

The workflow verifies the feature-contract checksum, the feature Parquet checksum against its evidence report, required governance columns, row counts, target consistency, non-empty eligibility populations, and strict chronological partition order. It writes an ignored eligibility Parquet file and an ignored JSON validation report atomically. The report records population counts and explicitly confirms that no healthy-negative class, fitted preprocessing, model, scores, alarms, or performance metrics were created.

## Bounded endpoint

This milestone ends when the committed contract, validation module, controlled tests, generated eligibility evidence, and professional documentation are verified and synchronized. Baseline fitting, threshold selection, validation analysis, test evaluation, model comparison, and performance reporting remain outside this milestone.

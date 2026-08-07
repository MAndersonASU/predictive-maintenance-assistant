# Machine-Learning Evaluation Report

## Evaluation design

The machine-learning workstream uses chronological, segment-safe governance and a frozen 48-feature set. A transparent maximum-absolute-robust-z-score detector is retained as the finalized benchmark. The advanced model family was restricted in advance to eight Isolation Forest candidates. The selected candidate was frozen after validation and then evaluated once on the locked test partition.

## Held-out comparison

| Measure | Isolation Forest | Robust-distance baseline |
|---|---:|---:|
| Documented-event coverage | 1.000 | 1.000 |
| Mean first-alarm latency, covered events (s) | 218.000 | 15804.000 |
| Alarms per 24 observed hours | 69.863 | 94.192 |

## Interpretation

This table is a transparent held-out comparison, not a test-driven model-selection step. No feature, threshold, model parameter, or candidate was changed after test access.

## Supported claims

The repository may report the governed operational measures above and the exact evaluation protocol. It must not report false-positive rate, accuracy, precision, recall, calibrated failure probability, or verified healthy-class performance because the project does not have a verified negative class supporting those claims.

## Frozen release decision

The advanced candidate remains `iforest_ne200_ms4096_mf1p0` because it was selected before test access. The robust-distance detector remains the transparent benchmark. Test evidence is final reporting evidence only.

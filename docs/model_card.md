# Model Card — MetroPT-3 Isolation Forest

## Intended use

This model is a bounded anomaly-detection component for the Intelligent Predictive Maintenance and Technical Knowledge Assistant. It scores governed MetroPT-3 compressor observations for unusualness. It does not estimate failure probability and does not create a verified healthy class.

## Frozen model

- Candidate: `iforest_ne200_ms4096_mf1p0`
- Family: `sklearn.ensemble.IsolationForest`
- Retained features: 48
- Frozen alarm threshold: `0.601902290159477`
- Model artifact SHA-256: `fa23b81d214161488abf601a8b9852f2467347e53d02fca3653a13cdaaaeec1a`
- Test-time refit: no
- Test-time threshold revision: no
- Test-driven candidate reselection: no

## Evaluation boundary

Model fitting and threshold derivation were training-only. Candidate selection was validation-only. The locked test partition was accessed once after explicit authorization and only after the candidate and threshold were frozen.

## Held-out evidence

- Eligible test rows scored: 429867
- Documented-event coverage: 1.000
- Mean first-alarm latency for covered events: 218.000 seconds
- Alarms per 24 observed hours: 69.863

## Limitations

- Unverified operational rows are not verified healthy negatives.
- Alarm burden is not a false-positive rate.
- Isolation Forest unusualness is not a failure probability.
- Documented-event evidence is limited to governed events present in the held-out partition.
- Held-out results cannot be used to retune this frozen release.

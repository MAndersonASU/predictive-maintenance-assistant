# Machine-Learning Subsystem Architecture

## Status

The machine-learning subsystem is implemented and frozen through its governed held-out evaluation. This file describes only the ML path. The current cross-workstream architecture, including the implemented technical-knowledge and grounding layers, is documented in [`system_architecture.md`](system_architecture.md).

```text
Governed MetroPT-3 Source
        |
        v
Checksum + Schema + Data-Quality Validation
        |
        v
Parquet + DuckDB Analytical Layer
        |
        v
Gap-Aware Target Materialization
        |
        v
Causal 48-Feature Frozen Set
        |
        +------------------------------+
        |                              |
        v                              v
Transparent Robust-Distance       Isolation Forest
Baseline                          Frozen Candidate Grid
        |                              |
        v                              v
One-Time Baseline Test           Validation-Only Selection
Evidence                              |
                                       v
                               Frozen Selected Model
                                       |
                                       v
                            One-Time Held-Out Test Evidence
                                       |
                                       v
                            ML Release Documentation
```

The robust-distance detector remains the transparent benchmark. The selected Isolation Forest candidate remains frozen at the validation-selected configuration and threshold. Held-out evidence is reporting evidence only and cannot be used for refitting, feature revision, threshold revision, or candidate reselection.

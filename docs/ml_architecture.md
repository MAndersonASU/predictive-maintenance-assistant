# Machine-Learning Architecture

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

The knowledge-retrieval, API, persistence, monitoring, Docker, and demonstration layers remain separate subsequent release milestones.

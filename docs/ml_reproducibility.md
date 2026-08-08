# Machine-Learning Reproducibility

## Safe environment verification

Run routine verification from the repository root with the project virtual environment active:

```powershell
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH = "src"
python -m pytest -q
python -m pip check
```

These commands do not fit models, score the held-out partition, or regenerate frozen release evidence.

## Frozen release identity

- Frozen candidate: `iforest_ne200_ms4096_mf1p0`
- Frozen threshold: `0.601902290159477`
- Model SHA-256: `fa23b81d214161488abf601a8b9852f2467347e53d02fca3653a13cdaaaeec1a`
- Held-out access: consumed exactly once under the governed release protocol
- Test-time refit: prohibited
- Test-time threshold revision: prohibited
- Test-driven candidate reselection: prohibited

## Held-out evaluator boundary

`predictive_maintenance.analysis.isolation_forest_test_evaluation` is retained for provenance and reproducibility of the governed implementation, but it is **not a routine verification command**.

The completed held-out evaluation must not be rerun or used to revise the frozen model, feature set, threshold, or candidate selection. Routine repository verification is limited to the controlled test suite, dependency checks, and non-production static checks.

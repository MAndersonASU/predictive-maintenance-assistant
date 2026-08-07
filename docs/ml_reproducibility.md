# Machine-Learning Reproducibility

Run commands from the repository root with the project virtual environment active.

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m predictive_maintenance.analysis.isolation_forest_test_evaluation
python -m predictive_maintenance.analysis.ml_release_documentation
```

The one-time test command must **not** be rerun after its governed outputs exist. The evaluator intentionally refuses overwrite.

Frozen candidate: `iforest_ne200_ms4096_mf1p0`
Frozen threshold: `0.601902290159477`
Model SHA-256: `fa23b81d214161488abf601a8b9852f2467347e53d02fca3653a13cdaaaeec1a`

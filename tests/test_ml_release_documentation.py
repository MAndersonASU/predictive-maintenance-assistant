from __future__ import annotations

import importlib

MODULE_NAME = "predictive_maintenance.analysis.ml_release_documentation"


def _report():
    return {
        "status": "frozen_after_one_time_test_evaluation",
        "governance": {"one_time_advanced_model_test_evaluation_complete": True},
        "frozen_model": {
            "candidate_id": "iforest_ne200_ms4096_mf1p0",
            "threshold": 0.601902290159477,
            "model_sha256": "abc",
            "retained_feature_count": 48,
        },
        "advanced_model_test": {
            "scored_rows": 100,
            "documented_event_coverage_fraction": 1.0,
            "mean_first_alarm_latency_seconds_for_covered_events": 30.0,
            "alarms_per_24_observed_hours": 4.0,
        },
        "baseline_comparison": {
            "isolation_forest": {
                "documented_event_coverage_fraction": 1.0,
                "mean_first_alarm_latency_seconds_for_covered_events": 30.0,
                "alarms_per_24_observed_hours": 4.0,
            },
            "robust_distance_baseline": {
                "documented_event_coverage_fraction": 0.5,
                "mean_first_alarm_latency_seconds_for_covered_events": 40.0,
                "alarms_per_24_observed_hours": 2.0,
            },
        },
    }


def test_build_documents_contains_only_ml_release_artifacts():
    module = importlib.import_module(MODULE_NAME)
    docs = module.build_documents(_report())
    assert set(docs) == {
        "docs/model_card.md",
        "docs/ml_evaluation_report.md",
        "docs/data_feature_governance.md",
        "docs/ml_architecture.md",
        "docs/ml_reproducibility.md",
    }


def test_model_card_preserves_non_probability_limitation():
    module = importlib.import_module(MODULE_NAME)
    assert "does not estimate failure probability" in module.build_documents(_report())["docs/model_card.md"]


def test_evaluation_report_says_not_reselection():
    module = importlib.import_module(MODULE_NAME)
    assert "not a test-driven model-selection step" in module.build_documents(_report())["docs/ml_evaluation_report.md"]


def test_generator_does_not_overwrite_repository_readme():
    module = importlib.import_module(MODULE_NAME)
    docs = module.build_documents(_report())
    assert "README.md" not in docs


def test_ml_architecture_is_explicitly_subsystem_scoped():
    module = importlib.import_module(MODULE_NAME)
    architecture = module.build_documents(_report())["docs/ml_architecture.md"]
    assert "Machine-Learning Subsystem Architecture" in architecture
    assert "system_architecture.md" in architecture


def test_reproducibility_warns_against_rerun():
    module = importlib.import_module(MODULE_NAME)
    assert "must **not** be rerun" in module.build_documents(_report())["docs/ml_reproducibility.md"]

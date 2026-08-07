from __future__ import annotations

import importlib

import pytest

MODULE_NAME = "predictive_maintenance.analysis.ml_release_log"


def _report():
    return {
        "status": "frozen_after_one_time_test_evaluation",
        "governance": {
            "one_time_advanced_model_test_evaluation_complete": True,
            "model_fitted_during_test_evaluation": False,
            "threshold_revised_using_test_evidence": False,
            "features_changed_using_test_evidence": False,
            "candidate_reselected_using_test_evidence": False,
            "unverified_rows_are_verified_healthy": False,
            "alarm_burden_is_false_positive_rate": False,
            "unusualness_is_failure_probability": False,
            "unsupported_classification_metrics_reported": False,
        },
        "frozen_model": {
            "candidate_id": "iforest_ne200_ms4096_mf1p0",
            "threshold": 0.601902290159477,
            "model_sha256": "abc",
            "retained_feature_count": 48,
        },
        "advanced_model_test": {
            "scored_rows": 10,
            "documented_event_count": 1,
            "documented_events_covered": 1,
            "scores_sha256": "scores",
        },
        "baseline_comparison": {
            "isolation_forest": {
                "documented_event_coverage_fraction": 1.0,
                "mean_first_alarm_latency_seconds_for_covered_events": 218.0,
                "alarms_per_24_observed_hours": 69.8,
            },
            "robust_distance_baseline": {
                "documented_event_coverage_fraction": 1.0,
                "mean_first_alarm_latency_seconds_for_covered_events": 15804.0,
                "alarms_per_24_observed_hours": 94.2,
            },
        },
    }


def _log():
    return """# Engineering Log

## Current Verified State

old state

## Implemented Milestones

history

## Current Engineering Workstream

old workstream

## Next Engineering Milestone

old milestone

## Robust-Distance Validation Baseline

baseline history
"""


def test_finalize_updates_current_sections():
    module = importlib.import_module(MODULE_NAME)
    sha = "a" * 40
    updated = module.finalize_log_text(
        _log(), _report(), sha, "Finalize release", 199, "reportsha"
    )
    assert f"Latest verified implementation commit: `{sha}`" in updated
    assert "Complete repository test suite: 199 passing tests" in updated
    assert "Advanced-model test access: consumed exactly once" in updated
    assert "Build the governed technical-document corpus" in updated


def test_finalize_appends_release_block_once():
    module = importlib.import_module(MODULE_NAME)
    sha = "b" * 40
    first = module.finalize_log_text(
        _log(), _report(), sha, "Finalize release", 199, "reportsha"
    )
    second = module.finalize_log_text(
        first, _report(), sha, "Finalize release", 199, "reportsha"
    )
    assert second.count(module.RELEASE_MARKER) == 1


def test_release_block_contains_baseline_comparison():
    module = importlib.import_module(MODULE_NAME)
    block = module.render_release_block(_report(), "c" * 40, 199, "reportsha")
    assert "15804.0 seconds" in block
    assert "94.2" in block
    assert "reportsha" in block


def test_invalid_commit_is_rejected():
    module = importlib.import_module(MODULE_NAME)
    with pytest.raises(module.MLReleaseLogError):
        module.finalize_log_text(
            _log(), _report(), "short", "Finalize release", 199, "reportsha"
        )


def test_empty_commit_message_is_rejected():
    module = importlib.import_module(MODULE_NAME)
    with pytest.raises(module.MLReleaseLogError):
        module.finalize_log_text(
            _log(), _report(), "d" * 40, " ", 199, "reportsha"
        )


def test_nonpositive_test_count_is_rejected():
    module = importlib.import_module(MODULE_NAME)
    with pytest.raises(module.MLReleaseLogError):
        module.finalize_log_text(
            _log(), _report(), "e" * 40, "Finalize release", 0, "reportsha"
        )

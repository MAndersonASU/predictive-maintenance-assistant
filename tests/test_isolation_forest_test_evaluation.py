from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

MODULE_NAME = "predictive_maintenance.analysis.isolation_forest_test_evaluation"


@pytest.fixture()
def module():
    return importlib.import_module(MODULE_NAME)


@pytest.fixture()
def contract():
    path = Path("config/metropt3_isolation_forest_test_evaluation.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_is_valid(module, contract):
    module.validate_contract(contract)


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorized_candidate_id", "other"),
        ("authorized_threshold", 0.5),
        ("one_time_test_evaluation_authorized", False),
    ],
)
def test_authorization_is_frozen(module, contract, field, value):
    changed = copy.deepcopy(contract)
    changed["authorization"][field] = value
    with pytest.raises(module.IsolationForestTestEvaluationError):
        module.validate_contract(changed)


def test_test_partition_is_frozen(module, contract):
    changed = copy.deepcopy(contract)
    changed["evaluation"]["partition"] = "validation"
    with pytest.raises(module.IsolationForestTestEvaluationError):
        module.validate_contract(changed)


@pytest.mark.parametrize(
    "field",
    [
        "candidate_reselection_enabled",
        "feature_changes_enabled",
        "test_driven_model_change_enabled",
        "unverified_rows_are_verified_healthy",
        "alarm_burden_is_false_positive_rate",
        "unusualness_is_failure_probability",
        "unsupported_classification_metrics_enabled",
    ],
)
def test_prohibited_governance_cannot_be_enabled(module, contract, field):
    changed = copy.deepcopy(contract)
    changed["governance"][field] = True
    with pytest.raises(module.IsolationForestTestEvaluationError):
        module.validate_contract(changed)


def test_score_summary(module):
    result = module._score_summary(np.asarray([1.0, 2.0, 3.0]))
    assert result["row_count"] == 3
    assert result["minimum"] == 1.0
    assert result["maximum"] == 3.0


def test_score_summary_rejects_nonfinite(module):
    with pytest.raises(module.IsolationForestTestEvaluationError):
        module._score_summary(np.asarray([1.0, np.nan]))


def test_event_evidence_reports_first_alarm_latency(module):
    timestamps = np.asarray(
        ["2020-01-01T00:00:00", "2020-01-01T00:00:10", "2020-01-01T00:00:20"],
        dtype="datetime64[s]",
    )
    events = np.asarray(["e1", "e1", "e1"])
    eligible = np.asarray([True, True, True])
    alarms = np.asarray([False, False, True])
    result = module._event_evidence(timestamps, events, eligible, alarms)
    assert result[0]["covered"] is True
    assert result[0]["first_alarm_latency_seconds"] == 20.0


def test_event_evidence_preserves_uncovered_event(module):
    timestamps = np.asarray(["2020-01-01T00:00:00"], dtype="datetime64[s]")
    result = module._event_evidence(
        timestamps,
        np.asarray(["e1"]),
        np.asarray([True]),
        np.asarray([False]),
    )
    assert result[0]["covered"] is False
    assert result[0]["first_alarm_latency_seconds"] is None


def test_baseline_mean_latency(module):
    test = {
        "documented_event_evidence": [
            {"covered": True, "first_alarm_latency_seconds": 10.0},
            {"covered": True, "first_alarm_latency_seconds": 30.0},
            {"covered": False, "first_alarm_latency_seconds": None},
        ]
    }
    assert module._baseline_mean_latency(test) == 20.0


def test_comparison_is_not_reselection(module):
    advanced = {
        "documented_event_coverage_fraction": 1.0,
        "mean_first_alarm_latency_seconds_for_covered_events": 10.0,
        "alarms_per_24_observed_hours": 20.0,
    }
    baseline = {
        "test": {
            "documented_event_coverage_fraction": 0.5,
            "documented_event_evidence": [
                {"covered": True, "first_alarm_latency_seconds": 25.0}
            ],
            "alarms_per_24_observed_hours": 5.0,
        }
    }
    result = module._comparison_summary(advanced, baseline)
    assert result["purpose"] == "held_out_evidence_comparison_not_model_reselection"
    assert result["test_evidence_used_for_candidate_reselection"] is False

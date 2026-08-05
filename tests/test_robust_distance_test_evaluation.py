import duckdb
import pytest

from predictive_maintenance.analysis.robust_distance_test_evaluation import (
    RobustDistanceTestEvaluationError,
    _score_expression,
    _validate_frozen_inputs,
    validate_contract,
)


def contract():
    return {
        "inputs": {},
        "evaluation": {
            "partition": "test",
            "selected_threshold_quantile": 0.995,
            "scoring_eligibility_column": "eligible_for_scoring",
            "known_event_eligibility_column": "eligible_for_known_event_evaluation",
            "alarm_burden_eligibility_column": "eligible_for_alarm_burden",
            "expected_sampling_seconds": 10.0,
        },
        "governance": {
            "parameters_must_be_frozen": True,
            "threshold_must_match_validation_decision": True,
            "validation_must_precede_test": True,
            "one_time_test_evaluation": True,
            "no_refit_or_threshold_revision": True,
            "unverified_rows_are_verified_healthy": False,
            "alarm_burden_is_false_positive_rate": False,
            "advanced_model_comparison_enabled": False,
        },
        "outputs": {"compression": "ZSTD"},
    }


def frozen_inputs():
    parameters = {
        "status": "frozen_before_validation",
        "test_partition_used": False,
        "threshold_quantile": 0.995,
        "threshold": 3.0,
        "retained_features": [
            {"feature": "x", "median": 0.0, "iqr": 1.0},
            {"feature": "y", "median": 2.0, "iqr": 2.0},
        ],
    }
    validation = {
        "status": "valid",
        "fit": {"threshold_quantile": 0.995, "threshold": 3.0},
        "governance": {"test_rows_scored": 0, "test_partition_locked": True},
    }
    diagnosis = {
        "status": "valid",
        "frozen_baseline": {"threshold": 3.0, "retained_feature_count": 2},
        "decision": {
            "selected_threshold_quantile": 0.995,
            "decision_status": "frozen_after_validation_diagnosis",
            "test_partition_remains_locked": True,
        },
    }
    return parameters, validation, diagnosis


def test_contract_accepts_governed_test_evaluation():
    validate_contract(contract())


@pytest.mark.parametrize(
    "control",
    [
        "parameters_must_be_frozen",
        "threshold_must_match_validation_decision",
        "validation_must_precede_test",
        "one_time_test_evaluation",
        "no_refit_or_threshold_revision",
    ],
)
def test_contract_rejects_disabled_required_control(control):
    payload = contract()
    payload["governance"][control] = False
    with pytest.raises(RobustDistanceTestEvaluationError):
        validate_contract(payload)


def test_contract_rejects_non_test_partition():
    payload = contract()
    payload["evaluation"]["partition"] = "validation"
    with pytest.raises(RobustDistanceTestEvaluationError):
        validate_contract(payload)


def test_contract_rejects_verified_healthy_claim():
    payload = contract()
    payload["governance"]["unverified_rows_are_verified_healthy"] = True
    with pytest.raises(RobustDistanceTestEvaluationError):
        validate_contract(payload)


def test_contract_rejects_false_positive_rate_claim():
    payload = contract()
    payload["governance"]["alarm_burden_is_false_positive_rate"] = True
    with pytest.raises(RobustDistanceTestEvaluationError):
        validate_contract(payload)


def test_contract_rejects_advanced_comparison():
    payload = contract()
    payload["governance"]["advanced_model_comparison_enabled"] = True
    with pytest.raises(RobustDistanceTestEvaluationError):
        validate_contract(payload)


def test_contract_rejects_invalid_sampling_seconds():
    payload = contract()
    payload["evaluation"]["expected_sampling_seconds"] = 0
    with pytest.raises(RobustDistanceTestEvaluationError):
        validate_contract(payload)


def test_contract_rejects_invalid_quantile():
    payload = contract()
    payload["evaluation"]["selected_threshold_quantile"] = 1.0
    with pytest.raises(RobustDistanceTestEvaluationError):
        validate_contract(payload)


def test_contract_rejects_unknown_compression():
    payload = contract()
    payload["outputs"]["compression"] = "BROTLI"
    with pytest.raises(RobustDistanceTestEvaluationError):
        validate_contract(payload)


def test_frozen_inputs_accept_matching_evidence_chain():
    retained, threshold = _validate_frozen_inputs(*frozen_inputs(), 0.995)
    assert [item["feature"] for item in retained] == ["x", "y"]
    assert threshold == 3.0


def test_frozen_inputs_reject_prior_test_use():
    parameters, validation, diagnosis = frozen_inputs()
    parameters["test_partition_used"] = True
    with pytest.raises(RobustDistanceTestEvaluationError):
        _validate_frozen_inputs(parameters, validation, diagnosis, 0.995)


def test_frozen_inputs_reject_validation_test_rows():
    parameters, validation, diagnosis = frozen_inputs()
    validation["governance"]["test_rows_scored"] = 1
    with pytest.raises(RobustDistanceTestEvaluationError):
        _validate_frozen_inputs(parameters, validation, diagnosis, 0.995)


def test_frozen_inputs_reject_unfrozen_diagnostic_decision():
    parameters, validation, diagnosis = frozen_inputs()
    diagnosis["decision"]["decision_status"] = "candidate"
    with pytest.raises(RobustDistanceTestEvaluationError):
        _validate_frozen_inputs(parameters, validation, diagnosis, 0.995)


def test_frozen_inputs_reject_quantile_mismatch():
    parameters, validation, diagnosis = frozen_inputs()
    diagnosis["decision"]["selected_threshold_quantile"] = 0.999
    with pytest.raises(RobustDistanceTestEvaluationError):
        _validate_frozen_inputs(parameters, validation, diagnosis, 0.995)


def test_frozen_inputs_reject_threshold_mismatch():
    parameters, validation, diagnosis = frozen_inputs()
    diagnosis["frozen_baseline"]["threshold"] = 4.0
    with pytest.raises(RobustDistanceTestEvaluationError):
        _validate_frozen_inputs(parameters, validation, diagnosis, 0.995)


def test_frozen_inputs_reject_retained_feature_count_mismatch():
    parameters, validation, diagnosis = frozen_inputs()
    diagnosis["frozen_baseline"]["retained_feature_count"] = 1
    with pytest.raises(RobustDistanceTestEvaluationError):
        _validate_frozen_inputs(parameters, validation, diagnosis, 0.995)


def test_score_expression_uses_maximum_absolute_robust_z_score():
    expression = _score_expression(
        [
            {"feature": "x", "median": 0.0, "iqr": 1.0},
            {"feature": "y", "median": 2.0, "iqr": 2.0},
        ]
    )
    connection = duckdb.connect(database=":memory:")
    try:
        value = connection.execute(
            f"SELECT {expression} FROM (SELECT 2.0 x, 10.0 y)"
        ).fetchone()[0]
    finally:
        connection.close()
    assert value == 4.0


def test_score_expression_rejects_nonpositive_iqr():
    with pytest.raises(RobustDistanceTestEvaluationError):
        _score_expression([{"feature": "x", "median": 0.0, "iqr": 0.0}])


def test_score_expression_rejects_duplicate_feature():
    with pytest.raises(RobustDistanceTestEvaluationError):
        _score_expression(
            [
                {"feature": "x", "median": 0.0, "iqr": 1.0},
                {"feature": "x", "median": 1.0, "iqr": 2.0},
            ]
        )

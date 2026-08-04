import duckdb
import pytest

from predictive_maintenance.analysis.robust_distance_diagnosis import (
    RobustDistanceDiagnosisError,
    _contribution_expression,
    _validate_frozen_inputs,
    validate_contract,
)


def contract():
    return {
        "inputs": {},
        "diagnosis": {
            "threshold_quantiles": [0.99, 0.995, 0.999],
            "selected_threshold_quantile": 0.995,
            "operating_state_features": [
                "COMP", "DV_eletric", "Towers", "MPG", "LPS",
                "Pressure_switch", "Oil_level", "Caudal_impulses",
            ],
            "top_operating_state_count": 32,
        },
        "governance": {
            "parameters_must_be_frozen": True,
            "threshold_candidates_training_derived_only": True,
            "validation_only_diagnosis": True,
            "test_partition_locked": True,
            "unverified_rows_are_verified_healthy": False,
            "alarm_burden_is_false_positive_rate": False,
        },
        "outputs": {},
    }


def test_contract_accepts_bounded_governed_candidates():
    validate_contract(contract())


@pytest.mark.parametrize("control", [
    "parameters_must_be_frozen", "threshold_candidates_training_derived_only",
    "validation_only_diagnosis", "test_partition_locked",
])
def test_contract_rejects_disabled_governance(control):
    payload = contract()
    payload["governance"][control] = False
    with pytest.raises(RobustDistanceDiagnosisError):
        validate_contract(payload)


def test_contract_rejects_verified_healthy_claim():
    payload = contract()
    payload["governance"]["unverified_rows_are_verified_healthy"] = True
    with pytest.raises(RobustDistanceDiagnosisError):
        validate_contract(payload)


def test_contract_rejects_false_positive_rate_claim():
    payload = contract()
    payload["governance"]["alarm_burden_is_false_positive_rate"] = True
    with pytest.raises(RobustDistanceDiagnosisError):
        validate_contract(payload)


def test_contract_rejects_unbounded_candidate_set():
    payload = contract()
    payload["diagnosis"]["threshold_quantiles"] = [0.9, 0.91, 0.92, 0.93, 0.94, 0.95]
    with pytest.raises(RobustDistanceDiagnosisError):
        validate_contract(payload)


def test_contract_rejects_selected_quantile_outside_candidates():
    payload = contract()
    payload["diagnosis"]["selected_threshold_quantile"] = 0.98
    with pytest.raises(RobustDistanceDiagnosisError):
        validate_contract(payload)


@pytest.mark.parametrize("features", [[], ["COMP", "COMP"], ["COMP", ""]])
def test_contract_rejects_invalid_operating_state_features(features):
    payload = contract()
    payload["diagnosis"]["operating_state_features"] = features
    with pytest.raises(RobustDistanceDiagnosisError):
        validate_contract(payload)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_contract_rejects_invalid_operating_state_limit(limit):
    payload = contract()
    payload["diagnosis"]["top_operating_state_count"] = limit
    with pytest.raises(RobustDistanceDiagnosisError):
        validate_contract(payload)


def test_frozen_inputs_accept_valid_validation_evidence():
    retained, threshold = _validate_frozen_inputs(
        {"status": "frozen_before_validation", "test_partition_used": False,
         "retained_features": [{"feature": "x", "median": 0.0, "iqr": 1.0}], "threshold": 3.0},
        {"status": "valid", "governance": {"test_rows_scored": 0}},
    )
    assert retained[0]["feature"] == "x"
    assert threshold == 3.0


def test_frozen_inputs_reject_test_use():
    with pytest.raises(RobustDistanceDiagnosisError):
        _validate_frozen_inputs(
            {"status": "frozen_before_validation", "test_partition_used": True,
             "retained_features": [], "threshold": 1.0},
            {"status": "valid", "governance": {"test_rows_scored": 0}},
        )


def test_contribution_expression_rejects_nonpositive_iqr():
    with pytest.raises(RobustDistanceDiagnosisError):
        _contribution_expression([{"feature": "x", "median": 0.0, "iqr": 0.0}])


def test_contribution_expression_identifies_largest_feature():
    expression = _contribution_expression([
        {"feature": "x", "median": 0.0, "iqr": 1.0},
        {"feature": "y", "median": 0.0, "iqr": 2.0},
    ])
    connection = duckdb.connect(database=":memory:")
    try:
        row = connection.execute(
            f"SELECT list_reduce({expression}, (best, item) -> CASE "
            "WHEN item.contribution > best.contribution THEN item ELSE best END) FROM (SELECT 2.0 x, 10.0 y)"
        ).fetchone()[0]
    finally:
        connection.close()
    assert row["feature"] == "y"
    assert row["contribution"] == 5.0

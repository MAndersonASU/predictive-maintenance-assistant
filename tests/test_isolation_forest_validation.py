"""Controlled tests for governed Isolation Forest training and validation."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.analysis.isolation_forest_validation import (
    IsolationForestValidationError,
    _longest_contiguous_alarm_run,
    _score_summary,
    build_candidate_grid,
    build_model,
    candidate_id,
    candidate_metrics,
    event_evidence,
    selection_key,
    validate_execution_contract,
)


def base_execution_contract() -> dict:
    return {
        "schema_version": 1,
        "comparison_contract": {
            "path": "config/metropt3_advanced_model_comparison.json",
            "validation_report_path": "outputs/metropt3_advanced_model_comparison_contract_report.json",
            "required_status": "valid",
        },
        "dataset": {
            "feature_parquet_path": "data/processed/metropt3_features.parquet",
            "feature_evidence_path": "outputs/metropt3_feature_engineering_report.json",
            "eligibility_parquet_path": "data/processed/metropt3_baseline_eligibility.parquet",
            "eligibility_evidence_path": "outputs/metropt3_baseline_evaluation_contract_report.json",
            "frozen_feature_parameters_path": "outputs/metropt3_robust_distance_parameters.json",
        },
        "execution": {
            "fit_partition": "train",
            "selection_partition": "validation",
            "fit_eligibility_column": "eligible_for_reference_fit",
            "scoring_eligibility_column": "eligible_for_scoring",
            "known_event_eligibility_column": "eligible_for_known_event_evaluation",
            "alarm_burden_eligibility_column": "eligible_for_alarm_burden",
            "expected_retained_feature_count": 48,
            "expected_sampling_seconds": 10.0,
            "matrix_dtype": "float32",
            "threshold_comparison": "strictly_greater_than",
        },
        "governance": {
            "model_fitting_enabled": True,
            "candidate_scoring_enabled": True,
            "candidate_selection_enabled": True,
            "validation_threshold_tuning_enabled": False,
            "test_partition_access_enabled": False,
            "test_scoring_enabled": False,
            "baseline_revision_enabled": False,
            "unsupported_classification_metrics_enabled": False,
            "unverified_rows_are_verified_healthy": False,
            "alarm_burden_is_false_positive_rate": False,
        },
        "outputs": {
            "selected_model": "outputs/metropt3_selected_isolation_forest.joblib",
            "selected_validation_scores": "data/processed/metropt3_validation_isolation_forest.parquet",
            "validation_decision_report": "outputs/metropt3_isolation_forest_validation_report.json",
            "parquet_compression": "zstd",
            "joblib_compression": 3,
        },
    }


def base_comparison_contract() -> dict:
    return {
        "candidate_model": {
            "fixed_parameters": {
                "contamination": "auto",
                "bootstrap": False,
                "random_state": 42,
                "n_jobs": -1,
            },
            "bounded_grid": {
                "n_estimators": [100, 200],
                "max_samples": [1024, 4096],
                "max_features": [0.5, 1.0],
            },
            "candidate_count": 8,
        }
    }


def result(coverage: float, latency: float | None, burden: float, rank: int) -> dict:
    return {
        "complexity_rank": rank,
        "metrics": {
            "documented_event_coverage": coverage,
            "mean_first_alarm_latency_seconds_for_covered_events": latency,
            "alarms_per_24_observed_hours": burden,
        },
    }


class IsolationForestValidationTests(unittest.TestCase):
    def test_valid_execution_contract(self) -> None:
        validate_execution_contract(base_execution_contract())

    def test_rejects_test_partition_access(self) -> None:
        contract = copy.deepcopy(base_execution_contract())
        contract["governance"]["test_partition_access_enabled"] = True
        with self.assertRaisesRegex(IsolationForestValidationError, "must be false"):
            validate_execution_contract(contract)

    def test_rejects_test_scoring(self) -> None:
        contract = copy.deepcopy(base_execution_contract())
        contract["governance"]["test_scoring_enabled"] = True
        with self.assertRaisesRegex(IsolationForestValidationError, "must be false"):
            validate_execution_contract(contract)

    def test_rejects_validation_threshold_tuning(self) -> None:
        contract = copy.deepcopy(base_execution_contract())
        contract["governance"]["validation_threshold_tuning_enabled"] = True
        with self.assertRaisesRegex(IsolationForestValidationError, "must be false"):
            validate_execution_contract(contract)

    def test_rejects_baseline_revision(self) -> None:
        contract = copy.deepcopy(base_execution_contract())
        contract["governance"]["baseline_revision_enabled"] = True
        with self.assertRaisesRegex(IsolationForestValidationError, "must be false"):
            validate_execution_contract(contract)

    def test_rejects_changed_feature_count(self) -> None:
        contract = copy.deepcopy(base_execution_contract())
        contract["execution"]["expected_retained_feature_count"] = 47
        with self.assertRaisesRegex(IsolationForestValidationError, "controls were changed"):
            validate_execution_contract(contract)

    def test_rejects_changed_fit_partition(self) -> None:
        contract = copy.deepcopy(base_execution_contract())
        contract["execution"]["fit_partition"] = "validation"
        with self.assertRaisesRegex(IsolationForestValidationError, "controls were changed"):
            validate_execution_contract(contract)

    def test_rejects_unverified_as_healthy(self) -> None:
        contract = copy.deepcopy(base_execution_contract())
        contract["governance"]["unverified_rows_are_verified_healthy"] = True
        with self.assertRaisesRegex(IsolationForestValidationError, "must be false"):
            validate_execution_contract(contract)

    def test_grid_has_exactly_eight_candidates(self) -> None:
        candidates = build_candidate_grid(base_comparison_contract())
        self.assertEqual(len(candidates), 8)
        self.assertEqual([item["complexity_rank"] for item in candidates], list(range(1, 9)))

    def test_grid_order_is_deterministic(self) -> None:
        candidates = build_candidate_grid(base_comparison_contract())
        self.assertEqual(candidates[0]["candidate_id"], "iforest_ne100_ms1024_mf0p5")
        self.assertEqual(candidates[-1]["candidate_id"], "iforest_ne200_ms4096_mf1p0")

    def test_grid_rejects_expansion(self) -> None:
        contract = base_comparison_contract()
        contract["candidate_model"]["bounded_grid"]["n_estimators"].append(400)
        contract["candidate_model"]["candidate_count"] = 12
        with self.assertRaisesRegex(IsolationForestValidationError, "exactly eight"):
            build_candidate_grid(contract)

    def test_candidate_id_is_stable(self) -> None:
        self.assertEqual(candidate_id(200, 4096, 0.5), "iforest_ne200_ms4096_mf0p5")

    def test_build_model_preserves_fixed_parameters(self) -> None:
        candidate = build_candidate_grid(base_comparison_contract())[0]
        model = build_model(candidate)
        self.assertEqual(model.n_estimators, 100)
        self.assertEqual(model.max_samples, 1024)
        self.assertEqual(model.max_features, 0.5)
        self.assertEqual(model.random_state, 42)
        self.assertEqual(model.n_jobs, -1)

    def test_selection_maximizes_coverage_first(self) -> None:
        stronger = result(1.0, 100.0, 500.0, 8)
        weaker = result(0.5, 0.0, 0.0, 1)
        self.assertLess(selection_key(stronger), selection_key(weaker))

    def test_selection_minimizes_latency_second(self) -> None:
        faster = result(1.0, 10.0, 500.0, 8)
        slower = result(1.0, 20.0, 0.0, 1)
        self.assertLess(selection_key(faster), selection_key(slower))

    def test_selection_minimizes_alarm_burden_third(self) -> None:
        lighter = result(1.0, 10.0, 5.0, 8)
        heavier = result(1.0, 10.0, 6.0, 1)
        self.assertLess(selection_key(lighter), selection_key(heavier))

    def test_selection_uses_complexity_last(self) -> None:
        simple = result(1.0, 10.0, 5.0, 1)
        complex_ = result(1.0, 10.0, 5.0, 8)
        self.assertLess(selection_key(simple), selection_key(complex_))

    def test_uncovered_latency_sorts_as_infinite(self) -> None:
        uncovered = result(0.0, None, 0.0, 1)
        covered = result(0.0, 10.0, 100.0, 8)
        self.assertLess(selection_key(covered), selection_key(uncovered))

    def test_score_summary(self) -> None:
        summary = _score_summary(np.array([1.0, 2.0, 3.0, 4.0]))
        self.assertEqual(summary["row_count"], 4)
        self.assertEqual(summary["minimum"], 1.0)
        self.assertEqual(summary["maximum"], 4.0)

    def test_score_summary_rejects_nonfinite(self) -> None:
        with self.assertRaisesRegex(IsolationForestValidationError, "finite"):
            _score_summary(np.array([1.0, np.nan]))

    def test_longest_contiguous_alarm_run_respects_gaps(self) -> None:
        times = np.array(
            [
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:10",
                "2026-01-01T00:00:20",
                "2026-01-01T00:01:00",
            ],
            dtype="datetime64[s]",
        )
        alarms = np.array([True, True, False, True])
        self.assertEqual(_longest_contiguous_alarm_run(times, alarms, 10.0), 2)

    def test_event_evidence_reports_coverage_and_latency(self) -> None:
        times = np.array(
            ["2026-01-01T00:00:00", "2026-01-01T00:00:10", "2026-01-01T00:00:20"],
            dtype="datetime64[s]",
        )
        evidence = event_evidence(
            times,
            np.array(["event_a", "event_a", "event_a"], dtype=object),
            np.array([True, True, True]),
            np.array([False, True, True]),
            10.0,
        )
        self.assertEqual(len(evidence), 1)
        self.assertTrue(evidence[0]["covered"])
        self.assertEqual(evidence[0]["first_alarm_latency_seconds"], 10.0)
        self.assertEqual(evidence[0]["longest_contiguous_alarm_run_rows"], 2)

    def test_candidate_metrics_uses_strict_threshold(self) -> None:
        times = np.array(
            ["2026-01-01T00:00:00", "2026-01-01T00:00:10", "2026-01-01T00:00:20"],
            dtype="datetime64[s]",
        )
        metrics, alarms = candidate_metrics(
            np.array([0.1, 0.2, 0.3]),
            np.array([0.5, 0.6, 0.7]),
            times,
            np.array(["event_a", "event_a", "event_a"], dtype=object),
            np.array([True, True, True]),
            np.array([False, False, False]),
            0.6,
            10.0,
        )
        self.assertEqual(alarms.tolist(), [False, False, True])
        self.assertEqual(metrics["documented_event_coverage"], 1.0)
        self.assertEqual(metrics["mean_first_alarm_latency_seconds_for_covered_events"], 20.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

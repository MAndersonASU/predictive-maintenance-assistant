"""Controlled tests for the governed advanced-model comparison contract."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.analysis.advanced_model_comparison import (
    AdvancedModelComparisonError,
    load_contract,
    validate_advanced_model_comparison,
    validate_contract,
    write_json_atomic,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_contract() -> dict:
    return {
        "schema_version": 1,
        "baseline_reference": {
            "source_commit": "1" * 40,
            "finalized": True,
            "family": "maximum_absolute_robust_z_score",
            "retained_feature_count": 48,
            "selected_threshold_quantile": 0.995,
            "frozen_threshold": 7857.013759410036,
            "committed_sources": [
                "config/metropt3_baseline_evaluation.json",
                "config/metropt3_robust_distance.json",
                "config/metropt3_robust_distance_diagnosis.json",
                "config/metropt3_robust_distance_test_evaluation.json",
            ],
            "generated_sources": [
                "outputs/metropt3_baseline_evaluation_contract_report.json",
                "outputs/metropt3_robust_distance_parameters.json",
                "outputs/metropt3_robust_distance_validation_report.json",
                "outputs/metropt3_robust_distance_diagnostic_report.json",
                "outputs/metropt3_robust_distance_test_report.json",
            ],
            "test_report": {
                "path": "outputs/metropt3_robust_distance_test_report.json",
                "sha256": "0" * 64,
                "design_or_tuning_use": "prohibited",
                "future_comparison_use": "reference_only_after_advanced_method_and_validation_decision_are_frozen",
            },
        },
        "population": {
            "partition_order": ["train", "validation", "test"],
            "development_partitions": ["train", "validation"],
            "test_partition_access_enabled": False,
            "fit_partition": "train",
            "selection_partition": "validation",
            "fit_eligibility_column": "eligible_for_reference_fit",
            "scoring_eligibility_column": "eligible_for_scoring",
            "known_event_eligibility_column": "eligible_for_known_event_evaluation",
            "alarm_burden_eligibility_column": "eligible_for_alarm_burden",
            "documented_positive_state": "documented_failure",
            "unlabeled_state": "unverified",
            "unverified_rows_are_verified_healthy": False,
            "require_no_exclusion_reason": True,
            "require_full_30_row_history": True,
            "chronological_only": True,
            "segment_safe": True,
            "partition_bounded": True,
        },
        "candidate_model": {
            "family": "isolation_forest",
            "implementation": "sklearn.ensemble.IsolationForest",
            "objective": "unsupervised_anomaly_scoring",
            "features": {
                "source": "frozen_robust_distance_retained_features",
                "count": 48,
                "same_features_for_every_candidate": True,
                "test_data_feature_selection_prohibited": True,
            },
            "preprocessing": {
                "fit_scope": "eligible_training_reference_rows_only",
                "missing_or_nonfinite_policy": "reject_before_fit",
                "scaling": "none",
                "validation_fit_prohibited": True,
                "test_fit_prohibited": True,
            },
            "fixed_parameters": {"contamination": "auto", "bootstrap": False, "random_state": 42, "n_jobs": -1},
            "bounded_grid": {
                "n_estimators": [100, 200],
                "max_samples": [1024, 4096],
                "max_features": [0.5, 1.0],
            },
            "candidate_count": 8,
            "score": {"method": "negative_score_samples", "direction": "higher_is_more_unusual"},
            "alarm_threshold": {
                "method": "eligible_training_score_quantile",
                "quantile": 0.995,
                "fit_partition": "train",
                "freeze_before_validation": True,
                "validation_threshold_tuning_prohibited": True,
                "test_threshold_tuning_prohibited": True,
            },
        },
        "validation_selection": {
            "partition": "validation",
            "test_evidence_available_to_selection": False,
            "rule": "lexicographic",
            "ordered_criteria": [
                {"metric": "documented_event_coverage", "direction": "maximize"},
                {"metric": "mean_first_alarm_latency_seconds_for_covered_events", "direction": "minimize"},
                {"metric": "alarms_per_24_observed_hours", "direction": "minimize"},
                {"metric": "candidate_complexity_rank", "direction": "minimize"},
            ],
            "complexity_tie_break_order": ["n_estimators", "max_samples", "max_features"],
            "supported_metrics": [
                "documented_event_coverage",
                "first_alarm_latency_seconds",
                "alarm_contiguity_within_documented_event",
                "alarm_burden_fraction",
                "alarms_per_24_observed_hours",
                "score_distribution_drift",
            ],
            "unsupported_metrics": [
                "accuracy",
                "precision",
                "recall_as_population_sensitivity",
                "specificity",
                "false_positive_rate",
                "roc_auc",
                "failure_probability",
            ],
            "alarm_burden_is_false_positive_rate": False,
        },
        "test_lock": {
            "locked": True,
            "one_time_future_evaluation": True,
            "baseline_test_evidence_cannot_select_candidate": True,
            "unlock_conditions": [
                "comparison_contract_validated",
                "candidate_implementation_tested",
                "bounded_grid_evaluated_on_validation_only",
                "winning_candidate_and_threshold_frozen",
                "validation_decision_report_checksummed",
                "explicit_separate_test_authorization",
            ],
        },
        "governance": {
            "model_fitting_enabled_for_this_validation": False,
            "learned_preprocessing_enabled_for_this_validation": False,
            "candidate_scoring_enabled_for_this_validation": False,
            "candidate_selection_enabled_for_this_validation": False,
            "advanced_test_evaluation_enabled_for_this_validation": False,
            "baseline_revision_enabled": False,
            "performance_claims_enabled_for_this_validation": False,
        },
        "outputs": {"validation_report": "outputs/metropt3_advanced_model_comparison_contract_report.json"},
    }


class AdvancedModelComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "contract.json"
        self.report = self.root / "outputs" / "comparison_report.json"
        contract = base_contract()
        for relative_path in contract["baseline_reference"]["committed_sources"]:
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"status": "controlled", "path": relative_path}) + "\n", encoding="utf-8")
        for relative_path in contract["baseline_reference"]["generated_sources"]:
            path = self.root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"status": "controlled", "path": relative_path}) + "\n", encoding="utf-8")
        test_report = self.root / contract["baseline_reference"]["test_report"]["path"]
        contract["baseline_reference"]["test_report"]["sha256"] = sha256(test_report)
        self.contract = contract
        self.config.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_workflow(self) -> dict:
        return validate_advanced_model_comparison(
            self.config,
            self.report,
            project_root=self.root,
        )

    def test_valid_contract_writes_no_training_report(self) -> None:
        report = self.run_workflow()
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["candidate_boundary"]["candidate_count"], 8)
        self.assertTrue(report["test_lock"]["locked"])
        self.assertFalse(report["scope"]["advanced_model_fitted"])
        self.assertFalse(report["scope"]["advanced_test_partition_accessed"])

    def test_load_contract_accepts_valid_file(self) -> None:
        loaded = load_contract(self.config)
        self.assertEqual(loaded["candidate_model"]["family"], "isolation_forest")

    def test_rejects_nonfinal_baseline(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["baseline_reference"]["finalized"] = False
        with self.assertRaisesRegex(AdvancedModelComparisonError, "finalized"):
            validate_contract(contract)

    def test_rejects_baseline_test_evidence_for_tuning(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["baseline_reference"]["test_report"]["design_or_tuning_use"] = "allowed"
        with self.assertRaisesRegex(AdvancedModelComparisonError, "prohibited"):
            validate_contract(contract)

    def test_rejects_baseline_feature_count_change(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["baseline_reference"]["retained_feature_count"] = 47
        with self.assertRaisesRegex(AdvancedModelComparisonError, "48"):
            validate_contract(contract)

    def test_rejects_test_partition_access(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["population"]["test_partition_access_enabled"] = True
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be false"):
            validate_contract(contract)

    def test_rejects_unverified_rows_as_healthy(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["population"]["unverified_rows_are_verified_healthy"] = True
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be false"):
            validate_contract(contract)

    def test_rejects_different_candidate_family(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["candidate_model"]["family"] = "one_class_svm"
        with self.assertRaisesRegex(AdvancedModelComparisonError, "isolation_forest"):
            validate_contract(contract)

    def test_rejects_test_based_feature_selection(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["candidate_model"]["features"]["test_data_feature_selection_prohibited"] = False
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be true"):
            validate_contract(contract)

    def test_rejects_validation_preprocessing_fit(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["candidate_model"]["preprocessing"]["validation_fit_prohibited"] = False
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be true"):
            validate_contract(contract)

    def test_rejects_unbounded_grid(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["candidate_model"]["bounded_grid"]["n_estimators"].append(400)
        with self.assertRaisesRegex(AdvancedModelComparisonError, "eight candidates"):
            validate_contract(contract)

    def test_rejects_candidate_count_mismatch(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["candidate_model"]["candidate_count"] = 9
        with self.assertRaisesRegex(AdvancedModelComparisonError, "candidate_count"):
            validate_contract(contract)

    def test_rejects_validation_threshold_tuning(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["candidate_model"]["alarm_threshold"]["validation_threshold_tuning_prohibited"] = False
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be true"):
            validate_contract(contract)

    def test_rejects_test_evidence_in_selection(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["validation_selection"]["test_evidence_available_to_selection"] = True
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be false"):
            validate_contract(contract)

    def test_rejects_reordered_selection_rule(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["validation_selection"]["ordered_criteria"].reverse()
        with self.assertRaisesRegex(AdvancedModelComparisonError, "selection criteria"):
            validate_contract(contract)

    def test_rejects_false_positive_rate_claim(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["validation_selection"]["alarm_burden_is_false_positive_rate"] = True
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be false"):
            validate_contract(contract)

    def test_rejects_unlocked_test(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["test_lock"]["locked"] = False
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be true"):
            validate_contract(contract)

    def test_rejects_premature_model_fitting(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["governance"]["model_fitting_enabled_for_this_validation"] = True
        with self.assertRaisesRegex(AdvancedModelComparisonError, "must be false"):
            validate_contract(contract)

    def test_missing_evidence_stops_before_report(self) -> None:
        missing = self.root / self.contract["baseline_reference"]["generated_sources"][0]
        missing.unlink()
        with self.assertRaisesRegex(AdvancedModelComparisonError, "does not exist"):
            self.run_workflow()
        self.assertFalse(self.report.exists())

    def test_test_report_checksum_mismatch_stops_before_report(self) -> None:
        test_report = self.root / self.contract["baseline_reference"]["test_report"]["path"]
        test_report.write_text('{"status":"changed"}\n', encoding="utf-8")
        with self.assertRaisesRegex(AdvancedModelComparisonError, "SHA-256"):
            self.run_workflow()
        self.assertFalse(self.report.exists())

    def test_existing_report_requires_overwrite(self) -> None:
        self.run_workflow()
        with self.assertRaisesRegex(AdvancedModelComparisonError, "--overwrite"):
            self.run_workflow()

    def test_atomic_json_has_final_newline(self) -> None:
        path = self.root / "atomic.json"
        write_json_atomic({"status": "valid"}, path)
        self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
        self.assertFalse(path.with_name("atomic.json.part").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

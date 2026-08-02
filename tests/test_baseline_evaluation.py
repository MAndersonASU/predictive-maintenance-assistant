"""Controlled tests for the governed baseline-evaluation contract."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.analysis.baseline_evaluation import (
    BaselineEvaluationError,
    validate_baseline_evaluation,
    validate_contract,
    write_json_atomic,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_contract() -> dict:
    return {
        "schema_version": 1,
        "dataset": {
            "name": "controlled",
            "feature_contract_path": "feature_contract.json",
            "feature_contract_sha256": "0" * 64,
            "feature_parquet_path": "features.parquet",
            "feature_evidence_path": "feature_report.json",
        },
        "population": {
            "partition_order": ["train", "validation", "test"],
            "documented_positive_state": "documented_failure",
            "unlabeled_reference_state": "unverified",
            "excluded_states": ["excluded_pre_event", "excluded_partition_buffer"],
            "require_no_exclusion_reason": True,
            "require_full_30_row_history": True,
            "unverified_rows_are_negative": False,
            "reference_population_interpretation": "unlabeled_operational_reference_not_verified_healthy",
        },
        "baseline": {
            "family": "training_reference_robust_distance",
            "feature_source": "numeric_model_features_excluding_governance_and_history_identifiers",
            "preprocessing": {
                "method": "median_and_interquartile_range",
                "fit_partition": "train",
                "fit_state": "unverified",
                "fit_on_eligible_reference_rows_only": True,
                "apply_frozen_parameters_to_later_partitions": True,
                "zero_iqr_policy": "exclude_feature_and_record_reason",
            },
            "score": {"method": "maximum_absolute_robust_z_score", "direction": "higher_is_more_unusual_relative_to_training_reference"},
            "alarm_threshold": {
                "method": "training_reference_score_quantile",
                "quantile": 0.995,
                "fit_partition": "train",
                "freeze_before_validation": True,
                "test_partition_locked_until_method_is_frozen": True,
            },
        },
        "evaluation": {
            "chronological_only": True,
            "segment_safe": True,
            "validation_precedes_test": True,
            "known_event_metrics": ["documented_event_coverage", "first_alarm_latency_seconds"],
            "unlabeled_operation_metrics": ["alarm_burden_fraction"],
            "unsupported_metrics": ["accuracy", "precision", "specificity", "false_positive_rate", "roc_auc"],
            "alarm_burden_is_false_positive_rate": False,
        },
        "governance": {
            "learned_preprocessing_enabled_for_this_validation": False,
            "model_fitting_enabled_for_this_validation": False,
            "score_generation_enabled_for_this_validation": False,
            "alarm_generation_enabled_for_this_validation": False,
            "performance_reporting_enabled_for_this_validation": False,
        },
        "outputs": {"eligibility_parquet": "eligibility.parquet", "validation_report": "report.json", "compression": "zstd"},
    }


class BaselineEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.feature_contract = self.root / "feature_contract.json"
        self.feature_contract.write_text('{"status":"controlled"}\n', encoding="utf-8")
        self.features = self.root / "features.parquet"
        self.feature_report = self.root / "feature_report.json"
        self.config = self.root / "contract.json"
        self.output = self.root / "eligibility.parquet"
        self.report = self.root / "report.json"

        connection = duckdb.connect(database=":memory:")
        try:
            connection.execute(
                f"""
                COPY (
                    SELECT * FROM (VALUES
                        (TIMESTAMP '2020-01-01 00:00:00', 1, 'train', 'unverified', NULL, NULL, NULL, true, 1.0),
                        (TIMESTAMP '2020-01-01 00:00:10', 1, 'train', 'documented_failure', 1, 'event_train', NULL, true, 2.0),
                        (TIMESTAMP '2020-02-01 00:00:00', 2, 'validation', 'unverified', NULL, NULL, NULL, true, 3.0),
                        (TIMESTAMP '2020-02-01 00:00:10', 2, 'validation', 'documented_failure', 1, 'event_validation', NULL, true, 4.0),
                        (TIMESTAMP '2020-03-01 00:00:00', 3, 'test', 'unverified', NULL, NULL, NULL, true, 5.0),
                        (TIMESTAMP '2020-03-01 00:00:10', 3, 'test', 'documented_failure', 1, 'event_test', NULL, true, 6.0),
                        (TIMESTAMP '2020-03-01 00:00:20', 3, 'test', 'excluded_pre_event', NULL, NULL, 'pre_event_exclusion', true, 7.0),
                        (TIMESTAMP '2020-03-01 00:00:30', 3, 'test', 'unverified', NULL, NULL, NULL, false, 8.0)
                    ) AS x(timestamp, segment_id, partition, target_state, binary_target, source_event, exclusion_reason, has_full_30_row_history, TP2)
                    ORDER BY timestamp
                ) TO '{self.features.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
        finally:
            connection.close()

        contract = base_contract()
        contract["dataset"]["feature_contract_sha256"] = sha256(self.feature_contract)
        self.config.write_text(json.dumps(contract), encoding="utf-8")
        self.feature_report.write_text(json.dumps({
            "status": "valid",
            "output": {"row_count": 8, "parquet_sha256": sha256(self.features)},
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_workflow(self) -> dict:
        return validate_baseline_evaluation(
            self.config,
            self.features,
            self.feature_report,
            self.output,
            self.report,
            feature_contract_path=self.feature_contract,
        )

    def test_contract_rejects_unverified_negative_class(self) -> None:
        contract = base_contract()
        contract["population"]["unverified_rows_are_negative"] = True
        with self.assertRaisesRegex(BaselineEvaluationError, "must not be treated as negatives"):
            validate_contract(contract)

    def test_contract_rejects_validation_fit(self) -> None:
        contract = base_contract()
        contract["baseline"]["preprocessing"]["fit_partition"] = "validation"
        with self.assertRaisesRegex(BaselineEvaluationError, "training rows only"):
            validate_contract(contract)

    def test_contract_rejects_unfrozen_threshold(self) -> None:
        contract = base_contract()
        contract["baseline"]["alarm_threshold"]["freeze_before_validation"] = False
        with self.assertRaisesRegex(BaselineEvaluationError, "training-only and frozen"):
            validate_contract(contract)

    def test_contract_blocks_premature_performance_reporting(self) -> None:
        contract = base_contract()
        contract["governance"]["performance_reporting_enabled_for_this_validation"] = True
        with self.assertRaisesRegex(BaselineEvaluationError, "must be false"):
            validate_contract(contract)

    def test_workflow_preserves_rows_and_scope(self) -> None:
        report = self.run_workflow()
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["input"]["row_count"], 8)
        self.assertEqual(report["output"]["row_count"], 8)
        self.assertFalse(report["scope"]["reference_population_is_verified_healthy"])
        self.assertFalse(report["scope"]["model_fitted"])
        self.assertFalse(report["scope"]["performance_metrics_reported"])

    def test_reference_fit_is_train_unlabeled_only(self) -> None:
        self.run_workflow()
        connection = duckdb.connect(database=":memory:")
        try:
            rows = connection.execute(
                f"SELECT partition, target_state FROM read_parquet('{self.output.as_posix()}') WHERE eligible_for_reference_fit"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(rows, [("train", "unverified")])

    def test_known_event_evaluation_excludes_training_event(self) -> None:
        self.run_workflow()
        connection = duckdb.connect(database=":memory:")
        try:
            rows = connection.execute(
                f"SELECT partition, source_event FROM read_parquet('{self.output.as_posix()}') WHERE eligible_for_known_event_evaluation ORDER BY timestamp"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(rows, [("validation", "event_validation"), ("test", "event_test")])

    def test_exclusions_and_incomplete_history_are_ineligible(self) -> None:
        self.run_workflow()
        connection = duckdb.connect(database=":memory:")
        try:
            count = connection.execute(
                f"SELECT count(*) FROM read_parquet('{self.output.as_posix()}') WHERE evaluation_role = 'excluded'"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 2)

    def test_feature_checksum_mismatch_stops_before_output(self) -> None:
        payload = json.loads(self.feature_report.read_text(encoding="utf-8"))
        payload["output"]["parquet_sha256"] = "f" * 64
        self.feature_report.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(BaselineEvaluationError, "SHA-256"):
            self.run_workflow()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.report.exists())

    def test_existing_output_requires_overwrite(self) -> None:
        self.run_workflow()
        with self.assertRaisesRegex(BaselineEvaluationError, "--overwrite"):
            self.run_workflow()

    def test_atomic_json_has_final_newline(self) -> None:
        path = self.root / "atomic.json"
        write_json_atomic({"status": "valid"}, path)
        self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
        self.assertFalse(path.with_name("atomic.json.part").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

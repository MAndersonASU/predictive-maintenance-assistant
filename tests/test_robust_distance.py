"""Controlled tests for the transparent robust-distance baseline."""

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

from predictive_maintenance.analysis.robust_distance import (
    RobustDistanceError,
    run_robust_distance,
    validate_contract,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_contract() -> dict:
    return {
        "schema_version": 1,
        "dataset": {
            "feature_contract_path": "feature_contract.json",
            "feature_parquet_path": "features.parquet",
            "feature_evidence_path": "feature_report.json",
            "eligibility_parquet_path": "eligibility.parquet",
            "eligibility_evidence_path": "eligibility_report.json",
        },
        "fit": {"partition": "train", "eligibility_column": "eligible_for_reference_fit", "location": "median", "scale": "interquartile_range", "zero_iqr_policy": "exclude_feature_and_record_reason"},
        "score": {"method": "maximum_absolute_robust_z_score", "threshold_quantile": 0.75, "threshold_fit_population": "eligible_training_reference_scores", "threshold_frozen_before_validation": True},
        "validation": {"partition": "validation", "test_partition_locked": True, "documented_positive_state": "documented_failure", "unlabeled_state": "unverified", "expected_sampling_seconds": 10.0},
        "outputs": {"parameters": "parameters.json", "validation_scores": "scores.parquet", "report": "report.json", "compression": "zstd"},
    }


class RobustDistanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.features = self.root / "features.parquet"
        self.eligibility = self.root / "eligibility.parquet"
        self.feature_report = self.root / "feature_report.json"
        self.eligibility_report = self.root / "eligibility_report.json"
        self.config = self.root / "contract.json"
        self.parameters = self.root / "parameters.json"
        self.scores = self.root / "scores.parquet"
        self.report = self.root / "report.json"
        connection = duckdb.connect(database=":memory:")
        try:
            connection.execute(f"""
                COPY (SELECT * FROM (VALUES
                    (TIMESTAMP '2020-01-01 00:00:00', 1, 'train', 'unverified', NULL, NULL, NULL, 1, 30, true, true, true, 0.0, 5.0),
                    (TIMESTAMP '2020-01-01 00:00:10', 1, 'train', 'unverified', NULL, NULL, NULL, 1, 31, true, true, true, 1.0, 5.0),
                    (TIMESTAMP '2020-01-01 00:00:20', 1, 'train', 'unverified', NULL, NULL, NULL, 1, 32, true, true, true, 2.0, 5.0),
                    (TIMESTAMP '2020-01-01 00:00:30', 1, 'train', 'unverified', NULL, NULL, NULL, 1, 33, true, true, true, 3.0, 5.0),
                    (TIMESTAMP '2020-02-01 00:00:00', 2, 'validation', 'unverified', NULL, NULL, NULL, 2, 30, true, true, true, 1.5, 5.0),
                    (TIMESTAMP '2020-02-01 00:00:10', 2, 'validation', 'documented_failure', 1, 'event_v', NULL, 2, 31, true, true, true, 10.0, 5.0),
                    (TIMESTAMP '2020-03-01 00:00:00', 3, 'test', 'documented_failure', 1, 'event_t', NULL, 3, 30, true, true, true, 100.0, 5.0)
                ) AS x(timestamp, segment_id, partition, target_state, binary_target, source_event, exclusion_reason, history_group_id, history_rows_available, has_lag_1_history, has_full_6_row_history, has_full_30_row_history, TP2, COMP))
                TO '{self.features.as_posix()}' (FORMAT PARQUET)
            """)
            connection.execute(f"""
                COPY (SELECT timestamp, segment_id, partition, target_state, binary_target, source_event, exclusion_reason, true AS has_full_30_row_history,
                    partition = 'train' AND target_state = 'unverified' AS eligible_for_reference_fit,
                    partition IN ('train', 'validation', 'test') AS eligible_for_scoring,
                    partition IN ('validation', 'test') AND target_state = 'documented_failure' AS eligible_for_known_event_evaluation,
                    partition IN ('validation', 'test') AND target_state = 'unverified' AS eligible_for_alarm_burden,
                    'controlled' AS evaluation_role
                FROM read_parquet('{self.features.as_posix()}'))
                TO '{self.eligibility.as_posix()}' (FORMAT PARQUET)
            """)
        finally:
            connection.close()
        self.feature_report.write_text(json.dumps({"status": "valid", "output": {"parquet_sha256": sha256(self.features)}}), encoding="utf-8")
        self.eligibility_report.write_text(json.dumps({"status": "valid", "output": {"parquet_sha256": sha256(self.eligibility)}}), encoding="utf-8")
        self.config.write_text(json.dumps(base_contract()), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_workflow(self) -> dict:
        return run_robust_distance(
            self.config, feature_path=self.features, feature_report_path=self.feature_report,
            eligibility_path=self.eligibility, eligibility_report_path=self.eligibility_report,
            parameters_path=self.parameters, scores_path=self.scores, report_path=self.report,
        )

    def test_rejects_nontraining_fit(self) -> None:
        contract = base_contract()
        contract["fit"]["partition"] = "validation"
        with self.assertRaisesRegex(RobustDistanceError, "training-reference"):
            validate_contract(contract)

    def test_rejects_unfrozen_threshold(self) -> None:
        contract = base_contract()
        contract["score"]["threshold_frozen_before_validation"] = False
        with self.assertRaisesRegex(RobustDistanceError, "frozen"):
            validate_contract(contract)

    def test_rejects_unlocked_test_partition(self) -> None:
        contract = base_contract()
        contract["validation"]["test_partition_locked"] = False
        with self.assertRaisesRegex(RobustDistanceError, "test partition"):
            validate_contract(contract)

    def test_zero_iqr_feature_is_recorded_and_excluded(self) -> None:
        self.run_workflow()
        payload = json.loads(self.parameters.read_text(encoding="utf-8"))
        self.assertEqual([item["feature"] for item in payload["excluded_features"]], ["COMP"])
        self.assertEqual([item["feature"] for item in payload["retained_features"]], ["TP2"])

    def test_parameters_fit_training_reference_only(self) -> None:
        report = self.run_workflow()
        self.assertEqual(report["fit"]["eligible_training_reference_rows"], 4)
        payload = json.loads(self.parameters.read_text(encoding="utf-8"))
        self.assertAlmostEqual(payload["retained_features"][0]["median"], 1.5)
        self.assertAlmostEqual(payload["retained_features"][0]["iqr"], 1.5)

    def test_threshold_is_training_derived_and_frozen(self) -> None:
        report = self.run_workflow()
        self.assertAlmostEqual(report["fit"]["threshold"], 1.0)
        self.assertTrue(report["governance"]["parameters_frozen_for_validation"])

    def test_scores_output_contains_validation_only(self) -> None:
        self.run_workflow()
        connection = duckdb.connect(database=":memory:")
        try:
            rows = connection.execute(f"SELECT timestamp FROM read_parquet('{self.scores.as_posix()}') ORDER BY timestamp").fetchall()
        finally:
            connection.close()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row[0].month == 2 for row in rows))

    def test_test_partition_remains_locked(self) -> None:
        report = self.run_workflow()
        self.assertTrue(report["governance"]["test_partition_locked"])
        self.assertEqual(report["governance"]["test_rows_scored"], 0)

    def test_documented_event_coverage_and_latency(self) -> None:
        report = self.run_workflow()
        self.assertEqual(report["validation"]["documented_event_count"], 1)
        self.assertEqual(report["validation"]["documented_events_covered"], 1)
        self.assertEqual(report["validation"]["documented_event_evidence"][0]["first_alarm_latency_seconds"], 0.0)

    def test_alarm_burden_is_not_false_positive_rate(self) -> None:
        report = self.run_workflow()
        self.assertFalse(report["governance"]["alarm_burden_is_false_positive_rate"])
        self.assertNotIn("false_positive_rate", report["validation"])

    def test_checksum_mismatch_stops_before_outputs(self) -> None:
        payload = json.loads(self.feature_report.read_text(encoding="utf-8"))
        payload["output"]["parquet_sha256"] = "f" * 64
        self.feature_report.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(RobustDistanceError, "SHA-256"):
            self.run_workflow()
        self.assertFalse(self.parameters.exists())
        self.assertFalse(self.scores.exists())
        self.assertFalse(self.report.exists())

    def test_existing_output_requires_overwrite(self) -> None:
        self.run_workflow()
        with self.assertRaisesRegex(RobustDistanceError, "--overwrite"):
            self.run_workflow()


if __name__ == "__main__":
    unittest.main(verbosity=2)

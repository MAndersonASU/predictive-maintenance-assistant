"""Controlled tests for causal, gap-aware MetroPT-3 feature engineering."""

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

from predictive_maintenance.analysis.feature_engineering import (
    FeatureEngineeringError,
    engineer_features,
    validate_contract,
    write_json_atomic,
)


CONTINUOUS = ["TP2", "TP3", "H1", "DV_pressure", "Reservoirs", "Oil_temperature", "Motor_current"]
STATES = ["COMP", "DV_eletric", "Towers", "MPG", "LPS", "Pressure_switch", "Oil_level", "Caudal_impulses"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_contract() -> dict:
    return {
        "schema_version": 1,
        "dataset": {"name": "controlled", "sensor_parquet_sha256": "0" * 64, "target_states_parquet_sha256": "0" * 64, "timestamp_column": "timestamp"},
        "feature_contract": {
            "causal_direction": "current_and_past_only", "continuous_signals": CONTINUOUS,
            "operating_state_signals": STATES, "include_current_values": True,
            "lag_rows": [1], "difference_lag_rows": 1, "rolling_windows_rows": [6, 30],
            "rolling_statistics": ["mean", "stddev_population"], "expected_sampling_seconds": 10.0,
            "history_reset_on_segment_change": True, "history_reset_on_partition_change": True,
            "rolling_windows_include_current_row": True, "partial_rolling_windows_allowed": True,
            "missing_history_policy": "null_lag_and_difference_with_explicit_history_indicators",
            "source_identifier_column_included": False,
        },
        "governance": {
            "preserve_target_columns": True, "unverified_rows_are_negative": False,
            "learned_preprocessing_enabled": False,
            "learned_preprocessing_fit_scope": "eligible_training_rows_only_if_enabled",
            "model_training_enabled": False, "performance_reporting_enabled": False,
        },
        "outputs": {"feature_parquet": "unused.parquet", "evidence_report": "unused.json", "compression": "zstd"},
    }


class FeatureEngineeringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sensor = self.root / "sensor.parquet"
        self.target = self.root / "target.parquet"
        self.output = self.root / "features.parquet"
        self.report = self.root / "report.json"
        self.config = self.root / "contract.json"
        connection = duckdb.connect(database=":memory:")
        try:
            sensor_values = []
            target_values = []
            rows = [
                ("2020-01-01 00:00:00", 1, "train", 1.0),
                ("2020-01-01 00:00:10", 1, "train", 2.0),
                ("2020-01-01 00:00:20", 1, None, 100.0),
                ("2020-01-01 00:00:30", 1, "validation", 4.0),
                ("2020-01-01 01:00:00", 2, "validation", 10.0),
                ("2020-01-01 01:00:10", 2, "validation", 12.0),
            ]
            for timestamp, segment, partition, value in rows:
                signals = ", ".join(str(value + i) for i in range(len(CONTINUOUS)))
                states = ", ".join(str(i % 2) for i in range(len(STATES)))
                sensor_values.append(f"(TIMESTAMP '{timestamp}', {signals}, {states})")
                partition_sql = "NULL" if partition is None else f"'{partition}'"
                target_values.append(f"(TIMESTAMP '{timestamp}', {segment}, {partition_sql}, 'unverified', NULL, NULL, {('NULL' if partition else "'chronological_partition_buffer'")})")
            sensor_columns = ", ".join(["timestamp"] + CONTINUOUS + STATES)
            connection.execute(f"COPY (SELECT * FROM (VALUES {', '.join(sensor_values)}) AS x({sensor_columns}) ORDER BY timestamp) TO '{self.sensor.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            target_columns = ", ".join(["timestamp", "segment_id", "partition", "target_state", "binary_target", "source_event", "exclusion_reason"])
            connection.execute(f"COPY (SELECT * FROM (VALUES {', '.join(target_values)}) AS x({target_columns}) ORDER BY timestamp) TO '{self.target.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        finally:
            connection.close()
        contract = base_contract()
        contract["dataset"]["sensor_parquet_sha256"] = sha256(self.sensor)
        contract["dataset"]["target_states_parquet_sha256"] = sha256(self.target)
        self.config.write_text(json.dumps(contract), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_workflow(self) -> dict:
        return engineer_features(self.config, self.sensor, self.target, self.output, self.report)

    def test_contract_rejects_future_direction(self) -> None:
        contract = base_contract()
        contract["feature_contract"]["causal_direction"] = "centered"
        with self.assertRaisesRegex(FeatureEngineeringError, "current_and_past_only"):
            validate_contract(contract)

    def test_contract_rejects_unverified_negative_class(self) -> None:
        contract = base_contract()
        contract["governance"]["unverified_rows_are_negative"] = True
        with self.assertRaisesRegex(FeatureEngineeringError, "must be false"):
            validate_contract(contract)

    def test_contract_rejects_learned_preprocessing(self) -> None:
        contract = base_contract()
        contract["governance"]["learned_preprocessing_enabled"] = True
        with self.assertRaisesRegex(FeatureEngineeringError, "disabled"):
            validate_contract(contract)

    def test_workflow_preserves_rows_governance_and_scope(self) -> None:
        report = self.run_workflow()
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["input"]["row_count"], 6)
        self.assertEqual(report["output"]["row_count"], 6)
        self.assertTrue(report["evidence"]["rows_preserved"])
        self.assertFalse(report["scope"]["unverified_rows_are_negative"])
        self.assertFalse(report["scope"]["models_trained"])
        self.assertTrue(self.output.exists())
        self.assertTrue(self.report.exists())

    def test_lag_difference_and_rolling_mean_are_causal(self) -> None:
        self.run_workflow()
        connection = duckdb.connect(database=":memory:")
        try:
            row = connection.execute(f"SELECT TP2__lag_1, TP2__delta_1, TP2__mean_6 FROM read_parquet('{self.output.as_posix()}') WHERE timestamp = TIMESTAMP '2020-01-01 00:00:10'").fetchone()
        finally:
            connection.close()
        self.assertEqual(row, (1.0, 1.0, 1.5))

    def test_partition_change_resets_history(self) -> None:
        self.run_workflow()
        connection = duckdb.connect(database=":memory:")
        try:
            row = connection.execute(f"SELECT history_rows_available, TP2__lag_1, TP2__mean_6 FROM read_parquet('{self.output.as_posix()}') WHERE timestamp = TIMESTAMP '2020-01-01 00:00:30'").fetchone()
        finally:
            connection.close()
        self.assertEqual(row[0], 1)
        self.assertIsNone(row[1])
        self.assertEqual(row[2], 4.0)

    def test_segment_change_resets_history(self) -> None:
        self.run_workflow()
        connection = duckdb.connect(database=":memory:")
        try:
            row = connection.execute(f"SELECT history_rows_available, TP2__lag_1 FROM read_parquet('{self.output.as_posix()}') WHERE timestamp = TIMESTAMP '2020-01-01 01:00:00'").fetchone()
        finally:
            connection.close()
        self.assertEqual(row[0], 1)
        self.assertIsNone(row[1])

    def test_checksum_mismatch_stops_before_output(self) -> None:
        contract = json.loads(self.config.read_text(encoding="utf-8"))
        contract["dataset"]["sensor_parquet_sha256"] = "f" * 64
        self.config.write_text(json.dumps(contract), encoding="utf-8")
        with self.assertRaisesRegex(FeatureEngineeringError, "mismatch"):
            self.run_workflow()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.report.exists())

    def test_existing_output_requires_overwrite(self) -> None:
        self.run_workflow()
        with self.assertRaisesRegex(FeatureEngineeringError, "--overwrite"):
            self.run_workflow()

    def test_atomic_json_has_newline_and_no_part_file(self) -> None:
        path = self.root / "atomic.json"
        write_json_atomic({"status": "valid"}, path)
        self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
        self.assertFalse(path.with_name("atomic.json.part").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

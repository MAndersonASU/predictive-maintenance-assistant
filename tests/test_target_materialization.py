"""Controlled tests for governed row-level target-state materialization."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import duckdb

from predictive_maintenance.analysis.target_materialization import (
    TargetMaterializationError,
    load_specification,
    materialize_targets,
    validate_materialization_policy,
    write_json_atomic,
)


BASE_SPEC = {
    "schema_version": 2,
    "dataset": {
        "name": "controlled MetroPT-3 sample",
        "source_identifier": "controlled:test",
        "parquet_sha256": "0" * 64,
        "start": "2020-01-01T00:00:00",
        "end": "2020-01-01T02:00:10",
    },
    "policy": {
        "minimum_warning_hours": 0.01,
        "partition_buffer_hours": 0.1,
        "unlabeled_rows_are_assumed_normal": False,
        "ambiguous_periods_are_excluded": True,
    },
    "materialization": {
        "timestamp_column": "timestamp",
        "expected_sampling_seconds": 10.0,
        "gap_threshold_seconds": 15.0,
        "pre_event_exclusion_hours": 0.01,
        "warning_horizon_hours": None,
        "cross_segment_assignment_allowed": False,
        "unverified_rows_are_negative": False,
        "source_conflicts_create_labels": False,
        "states": {
            "documented_failure": "documented_failure",
            "warning": "warning_not_enabled",
            "pre_event_exclusion": "excluded_pre_event",
            "partition_buffer_exclusion": "excluded_partition_buffer",
            "unverified": "unverified",
        },
    },
    "events": [
        {
            "name": "controlled_event",
            "start": "2020-01-01T02:00:00",
            "end": "2020-01-01T02:00:10",
            "prediction_window": None,
            "provenance": {
                "source_title": "Controlled source",
                "source_type": "controlled_test",
                "source_identifier": "controlled:test",
                "source_locator": "fixture",
                "accessed_on": "2026-08-01",
                "dataset_match": "exact",
                "confidence": "documented",
                "interpretation": "Controlled event interval.",
                "source_conflicts": ["Controlled conflict retained as metadata."],
            },
        }
    ],
    "evaluation": {
        "partitions": {
            "train": {
                "start": "2020-01-01T00:00:00",
                "end": "2020-01-01T00:00:20",
            },
            "validation": {
                "start": "2020-01-01T00:30:00",
                "end": "2020-01-01T00:30:10",
            },
            "test": {
                "start": "2020-01-01T01:59:40",
                "end": "2020-01-01T02:00:10",
            },
        },
        "leakage_controls": {
            "chronological_only": True,
            "segment_bounded_windows": True,
            "training_only_fit": True,
            "event_isolation": True,
        },
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def create_fixture(directory: Path, column: str = "timestamp") -> tuple[Path, dict]:
    parquet = directory / "input.parquet"
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute(
            f"""
            COPY (
                SELECT * FROM (VALUES
                    (TIMESTAMP '2020-01-01 00:00:00'),
                    (TIMESTAMP '2020-01-01 00:00:10'),
                    (TIMESTAMP '2020-01-01 00:00:20'),
                    (TIMESTAMP '2020-01-01 00:15:00'),
                    (TIMESTAMP '2020-01-01 00:30:00'),
                    (TIMESTAMP '2020-01-01 00:30:10'),
                    (TIMESTAMP '2020-01-01 01:00:00'),
                    (TIMESTAMP '2020-01-01 01:59:40'),
                    (TIMESTAMP '2020-01-01 01:59:50'),
                    (TIMESTAMP '2020-01-01 02:00:00'),
                    (TIMESTAMP '2020-01-01 02:00:10')
                ) AS sample({column})
                ORDER BY {column}
            ) TO '{parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )
    finally:
        connection.close()
    specification = copy.deepcopy(BASE_SPEC)
    specification["dataset"]["parquet_sha256"] = sha256(parquet)
    specification["materialization"]["timestamp_column"] = column
    return parquet, specification


class TargetMaterializationTests(unittest.TestCase):
    def test_policy_requires_explicit_nonnegative_control(self) -> None:
        payload = copy.deepcopy(BASE_SPEC)
        payload["materialization"]["unverified_rows_are_negative"] = True
        with self.assertRaisesRegex(TargetMaterializationError, "must be false"):
            validate_materialization_policy(payload)

    def test_warning_horizon_is_explicitly_disabled(self) -> None:
        policy = validate_materialization_policy(copy.deepcopy(BASE_SPEC))
        self.assertIsNone(policy.warning_horizon_hours)

    def test_warning_horizon_must_exceed_exclusion_buffer(self) -> None:
        payload = copy.deepcopy(BASE_SPEC)
        payload["materialization"]["warning_horizon_hours"] = 0.005
        with self.assertRaisesRegex(TargetMaterializationError, "must exceed"):
            validate_materialization_policy(payload)

    def test_gap_threshold_must_exceed_sampling_interval(self) -> None:
        payload = copy.deepcopy(BASE_SPEC)
        payload["materialization"]["gap_threshold_seconds"] = 10.0
        with self.assertRaisesRegex(TargetMaterializationError, "must exceed"):
            validate_materialization_policy(payload)

    def test_state_names_must_be_unique(self) -> None:
        payload = copy.deepcopy(BASE_SPEC)
        payload["materialization"]["states"]["unverified"] = "documented_failure"
        with self.assertRaisesRegex(TargetMaterializationError, "must be unique"):
            validate_materialization_policy(payload)

    def test_complete_materialization_preserves_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            parquet, specification = create_fixture(directory)
            specification_path = directory / "spec.json"
            specification_path.write_text(json.dumps(specification), encoding="utf-8")
            output = directory / "states.parquet"
            report_path = directory / "report.json"

            report = materialize_targets(
                specification_path, parquet, output, report_path
            )

            self.assertEqual(report["status"], "valid")
            self.assertEqual(report["input"]["row_count"], 11)
            self.assertEqual(report["output"]["row_count"], 11)
            self.assertEqual(report["evidence"]["segment_count"], 5)
            self.assertEqual(
                report["evidence"]["state_counts"]["documented_failure"], 2
            )
            self.assertEqual(
                report["evidence"]["state_counts"]["excluded_pre_event"], 2
            )
            self.assertGreater(
                report["evidence"]["state_counts"]["unverified"], 0
            )
            self.assertFalse(report["scope"]["verified_negative_class_created"])
            self.assertEqual(
                report["evidence"]["preserved_provenance_conflict_count"], 1
            )
            self.assertTrue(output.exists())
            self.assertTrue(report_path.exists())

    def test_pre_event_state_does_not_cross_gap(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            parquet, specification = create_fixture(directory)
            specification["materialization"]["pre_event_exclusion_hours"] = 1.1
            specification_path = directory / "spec.json"
            specification_path.write_text(json.dumps(specification), encoding="utf-8")
            output = directory / "states.parquet"
            report_path = directory / "report.json"
            materialize_targets(specification_path, parquet, output, report_path)

            connection = duckdb.connect(database=":memory:")
            try:
                state = connection.execute(
                    f"""
                    SELECT target_state
                    FROM read_parquet('{output.as_posix()}')
                    WHERE timestamp = TIMESTAMP '2020-01-01 01:00:00'
                    """
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(state, "excluded_partition_buffer")

    def test_checksum_mismatch_stops_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            parquet, specification = create_fixture(directory)
            specification["dataset"]["parquet_sha256"] = "f" * 64
            specification_path = directory / "spec.json"
            specification_path.write_text(json.dumps(specification), encoding="utf-8")
            output = directory / "states.parquet"
            report = directory / "report.json"
            with self.assertRaisesRegex(TargetMaterializationError, "SHA-256"):
                materialize_targets(specification_path, parquet, output, report)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())

    def test_timestamp_column_is_governed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            parquet, specification = create_fixture(directory, column="observed_at")
            specification["materialization"]["timestamp_column"] = "timestamp"
            specification_path = directory / "spec.json"
            specification_path.write_text(json.dumps(specification), encoding="utf-8")
            with self.assertRaisesRegex(TargetMaterializationError, "was not found"):
                materialize_targets(
                    specification_path,
                    parquet,
                    directory / "states.parquet",
                    directory / "report.json",
                )

    def test_specification_loader_rejects_non_object(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "spec.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(TargetMaterializationError, "must be an object"):
                load_specification(path)

    def test_atomic_json_has_final_newline_and_no_part_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "report.json"
            write_json_atomic({"status": "valid"}, path)
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
            self.assertFalse(path.with_name("report.json.part").exists())


if __name__ == "__main__":
    unittest.main()

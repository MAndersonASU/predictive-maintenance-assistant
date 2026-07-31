"""Controlled tests for target-definition and event-provenance validation."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from predictive_maintenance.analysis.target_definition import (
    TargetDefinitionError,
    load_and_validate,
    validate_specification,
    write_report_atomic,
)


VALID_SPEC = {
    "schema_version": 2,
    "dataset": {
        "name": "MetroPT-3 Air Production Unit",
        "source_identifier": "doi:10.24432/C5VW3R",
        "parquet_sha256": "a" * 64,
        "start": "2020-02-01T00:00:00",
        "end": "2020-09-01T03:59:50",
    },
    "policy": {
        "minimum_warning_hours": 2.0,
        "partition_buffer_hours": 2.0,
        "unlabeled_rows_are_assumed_normal": False,
        "ambiguous_periods_are_excluded": True,
    },
    "events": [
        {
            "name": "verified_event",
            "start": "2020-04-18T00:00:00",
            "end": "2020-04-18T23:59:00",
            "prediction_window": None,
            "provenance": {
                "source_title": "MetroPT-3 Dataset",
                "source_type": "exact_dataset_repository",
                "source_identifier": "doi:10.24432/C5VW3R",
                "source_locator": "Failure Information table, entry 1",
                "accessed_on": "2026-07-30",
                "dataset_match": "exact",
                "confidence": "documented",
                "interpretation": "Observed failure interval metadata.",
                "source_conflicts": [],
            },
        }
    ],
    "evaluation": {
        "partitions": {
            "train": {
                "start": "2020-02-01T00:00:00",
                "end": "2020-05-15T23:59:50",
            },
            "validation": {
                "start": "2020-05-16T02:00:00",
                "end": "2020-07-01T23:59:50",
            },
            "test": {
                "start": "2020-07-02T02:00:00",
                "end": "2020-09-01T03:59:50",
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


class TargetDefinitionTests(unittest.TestCase):
    def test_valid_specification_without_prediction_window(self) -> None:
        report = validate_specification(copy.deepcopy(VALID_SPEC))
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["documented_event_count"], 1)
        self.assertEqual(report["prediction_window_count"], 0)
        self.assertFalse(report["scope"]["row_level_labels_created"])

    def test_optional_prediction_window_is_counted(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["events"][0]["prediction_window"] = {
            "name": "verified_event_prediction_window",
            "start": "2020-04-17T18:00:00",
            "end": "2020-04-17T22:00:00",
        }
        report = validate_specification(payload)
        self.assertEqual(report["prediction_window_count"], 1)

    def test_prediction_window_must_precede_event(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["events"][0]["prediction_window"] = {
            "name": "invalid_window",
            "start": "2020-04-17T20:00:00",
            "end": "2020-04-18T00:00:00",
        }
        with self.assertRaisesRegex(TargetDefinitionError, "must end before"):
            validate_specification(payload)

    def test_minimum_warning_is_enforced(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["events"][0]["prediction_window"] = {
            "name": "insufficient_warning",
            "start": "2020-04-17T22:00:00",
            "end": "2020-04-17T23:00:00",
        }
        with self.assertRaisesRegex(TargetDefinitionError, "hours are required"):
            validate_specification(payload)

    def test_partitions_must_be_chronological(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["evaluation"]["partitions"]["validation"]["start"] = (
            "2020-05-01T00:00:00"
        )
        with self.assertRaisesRegex(TargetDefinitionError, "chronological"):
            validate_specification(payload)

    def test_all_leakage_controls_are_required(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["evaluation"]["leakage_controls"]["training_only_fit"] = False
        with self.assertRaisesRegex(TargetDefinitionError, "training_only_fit"):
            validate_specification(payload)

    def test_provenance_source_identifier_is_required(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        del payload["events"][0]["provenance"]["source_identifier"]
        with self.assertRaisesRegex(TargetDefinitionError, "source_identifier"):
            validate_specification(payload)

    def test_documented_event_requires_exact_dataset_match(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["events"][0]["provenance"]["dataset_match"] = "related"
        with self.assertRaisesRegex(TargetDefinitionError, "dataset_match is exact"):
            validate_specification(payload)

    def test_access_date_is_validated(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["events"][0]["provenance"]["accessed_on"] = "07/30/2026"
        with self.assertRaisesRegex(TargetDefinitionError, "YYYY-MM-DD"):
            validate_specification(payload)

    def test_source_conflicts_must_be_a_list(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["events"][0]["provenance"]["source_conflicts"] = "none"
        with self.assertRaisesRegex(TargetDefinitionError, "must be a list"):
            validate_specification(payload)

    def test_source_conflicts_are_counted(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["events"][0]["provenance"]["source_conflicts"] = [
            "Maintenance note date conflicts with the event date."
        ]
        report = validate_specification(payload)
        self.assertEqual(report["provenance_conflict_count"], 1)

    def test_observed_event_intervals_cannot_overlap(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        overlapping = copy.deepcopy(payload["events"][0])
        overlapping["name"] = "overlapping_event"
        overlapping["start"] = "2020-04-18T12:00:00"
        overlapping["end"] = "2020-04-19T01:00:00"
        payload["events"].append(overlapping)
        with self.assertRaisesRegex(TargetDefinitionError, "Observed event intervals overlap"):
            validate_specification(payload)

    def test_unlabeled_rows_cannot_be_assumed_normal(self) -> None:
        payload = copy.deepcopy(VALID_SPEC)
        payload["policy"]["unlabeled_rows_are_assumed_normal"] = True
        with self.assertRaisesRegex(TargetDefinitionError, "must be false"):
            validate_specification(payload)

    def test_file_loading_and_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            valid_path = Path(directory) / "valid.json"
            valid_path.write_text(json.dumps(VALID_SPEC), encoding="utf-8")
            self.assertEqual(load_and_validate(valid_path)["status"], "valid")

            invalid_path = Path(directory) / "invalid.json"
            invalid_path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(TargetDefinitionError, "Invalid JSON"):
                load_and_validate(invalid_path)

    def test_governed_configuration_has_four_documented_events(self) -> None:
        configuration = (
            Path(__file__).resolve().parents[1]
            / "config"
            / "metropt3_target_definition.json"
        )
        report = load_and_validate(configuration)
        self.assertEqual(report["event_count"], 4)
        self.assertEqual(report["documented_event_count"], 4)
        self.assertEqual(report["ambiguous_event_count"], 0)
        self.assertEqual(report["prediction_window_count"], 0)
        self.assertEqual(report["provenance_conflict_count"], 1)

    def test_atomic_report_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            write_report_atomic({"status": "valid"}, output)
            self.assertTrue(output.exists())
            self.assertTrue(output.read_text(encoding="utf-8").endswith("\n"))
            self.assertFalse(output.with_name("report.json.part").exists())


if __name__ == "__main__":
    unittest.main()

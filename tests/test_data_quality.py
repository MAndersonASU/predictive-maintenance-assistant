"""Controlled tests for the governed CSV data-quality profiler."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.data.acquire import EXPECTED_CSV_HEADER
from predictive_maintenance.data.data_quality import (
    DataQualityError,
    profile_csv,
    write_json_report,
)


class DataQualityProfileTests(unittest.TestCase):
    """Verify profiling behavior with small controlled CSV inputs."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temporary_directory.name)
        self.csv_path = self.temp_dir / "controlled.csv"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _base_row(self, timestamp: str, *, source_index: str = "0") -> list[str]:
        return [
            source_index,
            timestamp,
            "1.0",
            "2.0",
            "3.0",
            "4.0",
            "5.0",
            "6.0",
            "7.0",
            "1",
            "0",
            "1",
            "0",
            "1",
            "0",
            "1",
            "0",
        ]

    def _write_csv(
        self,
        rows: list[list[str]],
        header: tuple[str, ...] = EXPECTED_CSV_HEADER,
    ) -> Path:
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)
        return self.csv_path

    def test_valid_ordered_rows_report_regular_cadence(self) -> None:
        rows = [
            self._base_row("2020-01-01 00:00:00", source_index="0"),
            self._base_row("2020-01-01 00:00:01", source_index="1"),
            self._base_row("2020-01-01 00:00:02", source_index="2"),
        ]
        report = profile_csv(self._write_csv(rows))

        self.assertEqual(report["rows"]["data_row_count"], 3)
        self.assertEqual(report["schema"]["column_count"], 17)
        self.assertEqual(report["timestamps"]["expected_interval_seconds"], 1.0)
        self.assertEqual(report["timestamps"]["gap_count"], 0)
        self.assertTrue(report["timestamps"]["monotonic_non_decreasing"])
        self.assertFalse(report["source_preservation"]["source_modified"])

    def test_malformed_timestamp_is_counted(self) -> None:
        rows = [self._base_row("not-a-timestamp")]
        report = profile_csv(self._write_csv(rows))
        self.assertEqual(report["timestamps"]["parse_failure_count"], 1)

    def test_out_of_order_timestamp_is_counted(self) -> None:
        rows = [
            self._base_row("2020-01-01 00:00:02", source_index="0"),
            self._base_row("2020-01-01 00:00:01", source_index="1"),
        ]
        report = profile_csv(self._write_csv(rows))
        self.assertEqual(report["timestamps"]["out_of_order_count"], 1)
        self.assertFalse(report["timestamps"]["monotonic_non_decreasing"])

    def test_exact_duplicate_row_is_counted(self) -> None:
        duplicate = self._base_row("2020-01-01 00:00:00")
        report = profile_csv(self._write_csv([duplicate, duplicate]))
        self.assertEqual(report["rows"]["duplicate_row_count"], 1)

    def test_missing_cell_is_profiled_by_column(self) -> None:
        row = self._base_row("2020-01-01 00:00:00")
        row[2] = ""
        report = profile_csv(self._write_csv([row]))
        self.assertEqual(report["missing_values"]["by_column"]["TP2"], 1)
        self.assertEqual(report["missing_values"]["total_missing_value_count"], 1)

    def test_large_sampling_interval_is_reported_as_gap(self) -> None:
        rows = [
            self._base_row("2020-01-01 00:00:00", source_index="0"),
            self._base_row("2020-01-01 00:00:01", source_index="1"),
            self._base_row("2020-01-01 00:00:11", source_index="2"),
        ]
        report = profile_csv(self._write_csv(rows))
        self.assertEqual(report["timestamps"]["expected_interval_seconds"], 1.0)
        self.assertEqual(report["timestamps"]["gap_count"], 1)
        self.assertEqual(report["timestamps"]["largest_gap_seconds"], 10.0)
        self.assertEqual(len(report["timestamps"]["largest_gap_details"]), 1)

    def test_nonnumeric_sensor_value_is_counted(self) -> None:
        row = self._base_row("2020-01-01 00:00:00")
        row[2] = "bad-value"
        report = profile_csv(self._write_csv([row]))
        self.assertEqual(
            report["numeric_validation"]["coercion_failure_count_by_column"]["TP2"],
            1,
        )

    def test_unsupported_binary_value_is_counted(self) -> None:
        row = self._base_row("2020-01-01 00:00:00")
        row[9] = "2"
        report = profile_csv(self._write_csv([row]))
        self.assertEqual(
            report["binary_validation"]["invalid_value_count_by_column"]["COMP"],
            1,
        )
        self.assertEqual(
            report["binary_validation"]["invalid_values_by_column"]["COMP"]["2"],
            1,
        )

    def test_missing_input_file_raises_actionable_error(self) -> None:
        missing_path = self.temp_dir / "missing.csv"
        with self.assertRaisesRegex(DataQualityError, "does not exist"):
            profile_csv(missing_path)

    def test_missing_timestamp_column_raises_actionable_error(self) -> None:
        header = tuple(
            column for column in EXPECTED_CSV_HEADER if column != "timestamp"
        )
        row = ["0"] * len(header)
        self._write_csv([row], header=header)

        with self.assertRaisesRegex(DataQualityError, "timestamp.*missing"):
            profile_csv(self.csv_path, expected_header=None)


    def test_report_uses_nonempty_keys_for_unnamed_source_column(self) -> None:
        row = self._base_row("2020-01-01 00:00:00")
        report = profile_csv(self._write_csv([row]))

        report_key = report["schema"]["unnamed_column_report_key"]
        self.assertEqual(report_key, "__unnamed_column_0__")
        self.assertEqual(report["schema"]["columns"][0], "")
        self.assertNotIn("", report["missing_values"]["by_column"])
        self.assertNotIn(
            "",
            report["numeric_validation"][
                "coercion_failure_count_by_column"
            ],
        )
        self.assertIn(report_key, report["missing_values"]["by_column"])
        self.assertIn(
            report_key,
            report["numeric_validation"][
                "coercion_failure_count_by_column"
            ],
        )

    def test_json_report_is_written_with_final_newline(self) -> None:
        rows = [self._base_row("2020-01-01 00:00:00")]
        report = profile_csv(self._write_csv(rows))
        report_path = self.temp_dir / "report.json"

        completed_path = write_json_report(report, report_path)

        self.assertEqual(completed_path, report_path)
        self.assertTrue(report_path.exists())
        self.assertTrue(report_path.read_bytes().endswith(b"\n"))
        self.assertFalse((self.temp_dir / "report.json.part").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

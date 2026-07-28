"""Controlled tests for reproducible MetroPT-3 exploratory analysis."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.analysis.eda import (
    EDAError,
    OPERATING_STATE_FIGURE_FILENAME,
    OPERATING_STATE_FILENAME,
    SIGNAL_DISTRIBUTION_FIGURE_FILENAME,
    SIGNAL_SUMMARY_FILENAME,
    SUMMARY_FILENAME,
    TEMPORAL_GAP_FILENAME,
    TEMPORAL_SEGMENT_FILENAME,
    run_eda_workflow,
)
from predictive_maintenance.data.parquet_conversion import GOVERNED_ARROW_SCHEMA


class ExploratoryAnalysisTests(unittest.TestCase):
    """Verify EDA behavior using small governed Parquet inputs."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temporary_directory.name)
        self.parquet_path = self.temp_dir / "controlled.parquet"
        self.output_dir = self.temp_dir / "eda"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _row(
        self,
        timestamp: datetime,
        *,
        source_index: int,
        comp: float,
    ) -> dict[str, object]:
        return {
            "": source_index,
            "timestamp": timestamp,
            "TP2": 1.0 + source_index,
            "TP3": 2.0 + source_index,
            "H1": 3.0 + source_index,
            "DV_pressure": 4.0 + source_index,
            "Reservoirs": 5.0 + source_index,
            "Oil_temperature": 6.0 + source_index,
            "Motor_current": 7.0 + source_index,
            "COMP": comp,
            "DV_eletric": float(source_index % 2),
            "Towers": float((source_index + 1) % 2),
            "MPG": 0.0,
            "LPS": 1.0,
            "Pressure_switch": float(source_index % 2),
            "Oil_level": 1.0,
            "Caudal_impulses": 0.0,
        }

    def _write_governed_parquet(self) -> Path:
        start = datetime(2020, 1, 1, 0, 0, 0)
        timestamps = [
            start,
            start + timedelta(seconds=10),
            start + timedelta(seconds=20),
            start + timedelta(seconds=60),
            start + timedelta(seconds=70),
            start + timedelta(seconds=80),
        ]
        rows = [
            self._row(
                timestamp,
                source_index=index,
                comp=float(index >= 3),
            )
            for index, timestamp in enumerate(timestamps)
        ]
        table = pa.Table.from_pylist(rows, schema=GOVERNED_ARROW_SCHEMA)
        pq.write_table(table, self.parquet_path, compression="zstd")
        return self.parquet_path

    def _read_csv(self, filename: str) -> list[dict[str, str]]:
        with (self.output_dir / filename).open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            return list(csv.DictReader(handle))

    def test_complete_workflow_writes_gap_aware_outputs(self) -> None:
        self._write_governed_parquet()

        result = run_eda_workflow(
            self.parquet_path,
            self.output_dir,
        )

        self.assertEqual(result["processing_status"], "eda_completed")
        self.assertEqual(result["timestamp_coverage"]["row_count"], 6)
        self.assertEqual(result["temporal_analysis"]["gap_count"], 1)
        self.assertEqual(result["temporal_analysis"]["segment_count"], 2)
        self.assertEqual(
            [segment["row_count"] for segment in result["temporal_analysis"]["segments"]],
            [3, 3],
        )

        expected_files = (
            SUMMARY_FILENAME,
            SIGNAL_SUMMARY_FILENAME,
            OPERATING_STATE_FILENAME,
            TEMPORAL_SEGMENT_FILENAME,
            TEMPORAL_GAP_FILENAME,
        )
        for filename in expected_files:
            self.assertTrue((self.output_dir / filename).exists())

        self.assertTrue(
            (
                self.output_dir
                / "figures"
                / OPERATING_STATE_FIGURE_FILENAME
            ).exists()
        )
        self.assertTrue(
            (
                self.output_dir
                / "figures"
                / SIGNAL_DISTRIBUTION_FIGURE_FILENAME
            ).exists()
        )

    def test_signal_and_state_outputs_have_expected_records(self) -> None:
        self._write_governed_parquet()
        run_eda_workflow(self.parquet_path, self.output_dir)

        signal_rows = self._read_csv(SIGNAL_SUMMARY_FILENAME)
        operating_rows = self._read_csv(OPERATING_STATE_FILENAME)

        self.assertEqual(len(signal_rows), 7)
        self.assertEqual(signal_rows[0]["signal"], "TP2")

        comp_rows = [
            row for row in operating_rows if row["signal"] == "COMP"
        ]
        self.assertEqual(len(comp_rows), 2)
        self.assertEqual(
            sum(int(row["row_count"]) for row in comp_rows),
            6,
        )
        active = next(row for row in comp_rows if row["state"] == "1")
        self.assertAlmostEqual(float(active["percentage"]), 50.0)

    def test_summary_records_configuration_schema_and_scope(self) -> None:
        self._write_governed_parquet()
        run_eda_workflow(
            self.parquet_path,
            self.output_dir,
            gap_threshold_seconds=20.0,
            max_gap_details=5,
        )

        summary = json.loads(
            (self.output_dir / SUMMARY_FILENAME).read_text(encoding="utf-8")
        )

        self.assertEqual(summary["configuration"]["gap_threshold_seconds"], 20.0)
        self.assertEqual(summary["configuration"]["max_gap_details"], 5)
        self.assertEqual(summary["schema"]["column_count"], 17)
        self.assertEqual(summary["schema"]["columns"][1]["name"], "timestamp")
        self.assertEqual(len(summary["scope_limits"]), 3)
        self.assertIn("duckdb", summary["software"])

    def test_existing_outputs_require_explicit_overwrite(self) -> None:
        self._write_governed_parquet()
        run_eda_workflow(self.parquet_path, self.output_dir)

        with self.assertRaisesRegex(EDAError, "output already exists"):
            run_eda_workflow(self.parquet_path, self.output_dir)

        result = run_eda_workflow(
            self.parquet_path,
            self.output_dir,
            overwrite=True,
        )
        self.assertEqual(result["processing_status"], "eda_completed")

    def test_missing_parquet_raises_actionable_error(self) -> None:
        with self.assertRaisesRegex(EDAError, "does not exist"):
            run_eda_workflow(
                self.temp_dir / "missing.parquet",
                self.output_dir,
            )

    def test_unexpected_schema_is_rejected(self) -> None:
        table = pa.table(
            {
                "timestamp": [datetime(2020, 1, 1, 0, 0, 0)],
                "TP2": [1.0],
            }
        )
        pq.write_table(table, self.parquet_path)

        with self.assertRaisesRegex(EDAError, "verified analytical schema"):
            run_eda_workflow(self.parquet_path, self.output_dir)

    def test_partial_files_are_not_left_after_success(self) -> None:
        self._write_governed_parquet()
        run_eda_workflow(self.parquet_path, self.output_dir)

        partial_files = list(self.output_dir.rglob("*.part"))
        self.assertEqual(partial_files, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

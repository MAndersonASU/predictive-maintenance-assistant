"""Controlled tests for governed CSV-to-Parquet processing."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.data.acquire import (
    EXPECTED_CSV_HEADER,
    calculate_sha256,
)
from predictive_maintenance.data.parquet_conversion import (
    EXPECTED_DUCKDB_COLUMNS,
    GOVERNED_ARROW_SCHEMA,
    ParquetConversionError,
    build_conversion_metadata,
    convert_csv_to_parquet,
    inspect_parquet_with_duckdb,
    run_conversion_workflow,
    write_conversion_metadata,
)


class ParquetConversionTests(unittest.TestCase):
    """Verify conversion behavior using small controlled CSV inputs."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temporary_directory.name)
        self.csv_path = self.temp_dir / "controlled.csv"
        self.parquet_path = self.temp_dir / "controlled.parquet"
        self.metadata_path = self.temp_dir / "conversion_metadata.json"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _base_row(
        self,
        timestamp: str,
        *,
        source_index: str = "0",
    ) -> list[str]:
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

    def _write_csv(self, rows: list[list[str]]) -> Path:
        with self.csv_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(EXPECTED_CSV_HEADER)
            writer.writerows(rows)

        return self.csv_path

    def _two_valid_rows(self) -> list[list[str]]:
        return [
            self._base_row(
                "2020-01-01 00:00:00",
                source_index="0",
            ),
            self._base_row(
                "2020-01-01 00:00:10",
                source_index="10",
            ),
        ]

    def test_valid_csv_converts_with_preserved_rows_and_schema(
        self,
    ) -> None:
        self._write_csv(self._two_valid_rows())

        source_checksum_before = calculate_sha256(self.csv_path)

        result = convert_csv_to_parquet(
            self.csv_path,
            self.parquet_path,
            expected_row_count=2,
        )

        source_checksum_after = calculate_sha256(self.csv_path)
        parquet_schema = pq.read_schema(self.parquet_path)
        parquet_metadata = pq.read_metadata(self.parquet_path)

        self.assertTrue(self.parquet_path.exists())
        self.assertFalse(
            (self.temp_dir / "controlled.parquet.part").exists()
        )

        self.assertEqual(source_checksum_after, source_checksum_before)
        self.assertFalse(result["source_modified"])
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["column_count"], 17)
        self.assertEqual(result["compression"], "zstd")

        self.assertEqual(parquet_metadata.num_rows, 2)
        self.assertEqual(parquet_metadata.num_columns, 17)
        self.assertEqual(
            tuple(parquet_schema.names),
            EXPECTED_CSV_HEADER,
        )
        self.assertTrue(
            parquet_schema.equals(
                GOVERNED_ARROW_SCHEMA,
                check_metadata=False,
            )
        )

    def test_row_count_mismatch_removes_partial_output(self) -> None:
        self._write_csv(self._two_valid_rows())

        with self.assertRaisesRegex(
            ParquetConversionError,
            "row count does not match",
        ):
            convert_csv_to_parquet(
                self.csv_path,
                self.parquet_path,
                expected_row_count=3,
            )

        self.assertFalse(self.parquet_path.exists())
        self.assertFalse(
            (self.temp_dir / "controlled.parquet.part").exists()
        )

    def test_missing_source_raises_actionable_error(self) -> None:
        missing_path = self.temp_dir / "missing.csv"

        with self.assertRaisesRegex(
            ParquetConversionError,
            "does not exist",
        ):
            convert_csv_to_parquet(
                missing_path,
                self.parquet_path,
                expected_row_count=2,
            )

        self.assertFalse(self.parquet_path.exists())

    def test_existing_destination_requires_explicit_overwrite(
        self,
    ) -> None:
        self._write_csv(self._two_valid_rows())

        convert_csv_to_parquet(
            self.csv_path,
            self.parquet_path,
            expected_row_count=2,
        )

        existing_checksum = calculate_sha256(self.parquet_path)

        with self.assertRaisesRegex(
            ParquetConversionError,
            "already exists",
        ):
            convert_csv_to_parquet(
                self.csv_path,
                self.parquet_path,
                expected_row_count=2,
            )

        self.assertEqual(
            calculate_sha256(self.parquet_path),
            existing_checksum,
        )

    def test_conversion_metadata_is_complete_and_written_atomically(
        self,
    ) -> None:
        self._write_csv(self._two_valid_rows())

        conversion_result = convert_csv_to_parquet(
            self.csv_path,
            self.parquet_path,
            expected_row_count=2,
        )

        duckdb_inspection = inspect_parquet_with_duckdb(
            self.parquet_path
        )

        metadata = build_conversion_metadata(
            conversion_result,
            duckdb_inspection,
        )

        completed_path = write_conversion_metadata(
            metadata,
            self.metadata_path,
        )

        saved_metadata = json.loads(
            self.metadata_path.read_text(encoding="utf-8")
        )

        self.assertEqual(completed_path, self.metadata_path)
        self.assertTrue(self.metadata_path.exists())
        self.assertTrue(
            self.metadata_path.read_bytes().endswith(b"\n")
        )
        self.assertFalse(
            (
                self.temp_dir
                / "conversion_metadata.json.part"
            ).exists()
        )

        self.assertEqual(
            saved_metadata["processing_status"],
            "converted_and_verified",
        )
        self.assertEqual(saved_metadata["output"]["row_count"], 2)
        self.assertEqual(saved_metadata["output"]["column_count"], 17)
        self.assertEqual(
            saved_metadata["configuration"]["compression"],
            "zstd",
        )
        self.assertEqual(
            saved_metadata["source"]["sha256"],
            calculate_sha256(self.csv_path),
        )
        self.assertEqual(
            saved_metadata["output"]["sha256"],
            calculate_sha256(self.parquet_path),
        )
        self.assertFalse(
            saved_metadata["source_preservation"]["source_modified"]
        )
        self.assertEqual(
            saved_metadata["schema"]["duckdb_unnamed_column_alias"],
            "C0",
        )

    def test_duckdb_reads_parquet_rows_and_schema(self) -> None:
        self._write_csv(self._two_valid_rows())

        convert_csv_to_parquet(
            self.csv_path,
            self.parquet_path,
            expected_row_count=2,
        )

        inspection = inspect_parquet_with_duckdb(
            self.parquet_path
        )

        column_names = tuple(
            column["name"]
            for column in inspection["columns"]
        )

        self.assertEqual(inspection["row_count"], 2)
        self.assertEqual(inspection["column_count"], 17)
        self.assertEqual(inspection["database"], ":memory:")
        self.assertEqual(
            column_names,
            EXPECTED_DUCKDB_COLUMNS,
        )
        self.assertEqual(
            inspection["columns"][1]["duckdb_type"],
            "TIMESTAMP",
        )

    def test_complete_workflow_creates_verified_outputs(self) -> None:
        self._write_csv(self._two_valid_rows())

        result = run_conversion_workflow(
            csv_path=self.csv_path,
            parquet_path=self.parquet_path,
            metadata_path=self.metadata_path,
            expected_row_count=2,
        )

        self.assertEqual(
            result["processing_status"],
            "converted_and_verified",
        )
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["column_count"], 17)
        self.assertEqual(result["compression"], "zstd")
        self.assertTrue(self.parquet_path.exists())
        self.assertTrue(self.metadata_path.exists())

        saved_metadata = json.loads(
            self.metadata_path.read_text(encoding="utf-8")
        )

        self.assertEqual(
            saved_metadata["duckdb_validation"]["row_count"],
            2,
        )
        self.assertEqual(
            saved_metadata["duckdb_validation"]["column_count"],
            17,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
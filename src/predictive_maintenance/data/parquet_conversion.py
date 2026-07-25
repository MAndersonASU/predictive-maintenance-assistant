"""Deterministic CSV-to-Parquet conversion and DuckDB validation."""

from __future__ import annotations

import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pyarrow
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

try:
    from .acquire import (
        DATASET_CSV_PATH,
        EXPECTED_CSV_HEADER,
        calculate_sha256,
    )
except ImportError:  # Supports direct execution from this source directory.
    from acquire import (
        DATASET_CSV_PATH,
        EXPECTED_CSV_HEADER,
        calculate_sha256,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[3]

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

DEFAULT_PARQUET_PATH = (
    PROCESSED_DATA_DIR / "metropt3_air_compressor.parquet"
)

DEFAULT_METADATA_PATH = (
    PROJECT_ROOT / "outputs" / "metropt3_parquet_metadata.json"
)

PARQUET_COMPRESSION = "zstd"
CSV_BLOCK_SIZE_BYTES = 16 * 1024 * 1024

VERIFIED_SOURCE_ROW_COUNT = 1_516_948

GOVERNED_ARROW_SCHEMA = pa.schema(
    [
        pa.field("", pa.int64()),
        pa.field("timestamp", pa.timestamp("ms")),
        pa.field("TP2", pa.float64()),
        pa.field("TP3", pa.float64()),
        pa.field("H1", pa.float64()),
        pa.field("DV_pressure", pa.float64()),
        pa.field("Reservoirs", pa.float64()),
        pa.field("Oil_temperature", pa.float64()),
        pa.field("Motor_current", pa.float64()),
        pa.field("COMP", pa.float64()),
        pa.field("DV_eletric", pa.float64()),
        pa.field("Towers", pa.float64()),
        pa.field("MPG", pa.float64()),
        pa.field("LPS", pa.float64()),
        pa.field("Pressure_switch", pa.float64()),
        pa.field("Oil_level", pa.float64()),
        pa.field("Caudal_impulses", pa.float64()),
    ]
)

EXPECTED_DUCKDB_COLUMNS = (
    "C0",
    *EXPECTED_CSV_HEADER[1:],
)


class ParquetConversionError(RuntimeError):
    """Raised when governed CSV-to-Parquet processing cannot be completed."""


def _validate_source_file(csv_path: Path) -> None:
    """Validate that the governed CSV source exists and is readable."""

    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise ParquetConversionError(
            f"CSV source does not exist: {csv_path}"
        )

    if not csv_path.is_file():
        raise ParquetConversionError(
            f"CSV source path is not a file: {csv_path}"
        )

    if csv_path.stat().st_size == 0:
        raise ParquetConversionError(
            f"CSV source is empty: {csv_path}"
        )


def _schema_as_records(schema: pa.Schema) -> list[dict[str, str]]:
    """Return an Arrow schema in a JSON-compatible representation."""

    return [
        {
            "name": field.name,
            "arrow_type": str(field.type),
        }
        for field in schema
    ]


def _validate_parquet_output(
    parquet_path: Path,
    *,
    expected_row_count: int,
) -> dict[str, Any]:
    """Validate row count and schema for a completed Parquet output."""

    try:
        parquet_metadata = pq.read_metadata(parquet_path)
        parquet_schema = pq.read_schema(parquet_path)
    except (OSError, pa.ArrowException) as error:
        raise ParquetConversionError(
            f"Unable to inspect Parquet output: {parquet_path}"
        ) from error

    if parquet_metadata.num_rows != expected_row_count:
        raise ParquetConversionError(
            "Parquet metadata row count does not match the converted count: "
            f"expected {expected_row_count}, "
            f"received {parquet_metadata.num_rows}"
        )

    if parquet_metadata.num_columns != len(GOVERNED_ARROW_SCHEMA):
        raise ParquetConversionError(
            "Parquet column count does not match the governed schema: "
            f"expected {len(GOVERNED_ARROW_SCHEMA)}, "
            f"received {parquet_metadata.num_columns}"
        )

    if not parquet_schema.equals(
        GOVERNED_ARROW_SCHEMA,
        check_metadata=False,
    ):
        raise ParquetConversionError(
            "Parquet schema does not match the governed Arrow schema.\n"
            f"Expected: {GOVERNED_ARROW_SCHEMA}\n"
            f"Actual:   {parquet_schema}"
        )

    return {
        "row_count": parquet_metadata.num_rows,
        "column_count": parquet_metadata.num_columns,
        "row_group_count": parquet_metadata.num_row_groups,
        "format_version": parquet_metadata.format_version,
        "created_by": parquet_metadata.created_by,
        "schema": _schema_as_records(parquet_schema),
    }


def convert_csv_to_parquet(
    csv_path: Path = DATASET_CSV_PATH,
    parquet_path: Path = DEFAULT_PARQUET_PATH,
    *,
    expected_row_count: int | None = VERIFIED_SOURCE_ROW_COUNT,
    compression: str = PARQUET_COMPRESSION,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Convert a governed CSV to validated Parquet using an explicit schema."""

    csv_path = Path(csv_path)
    parquet_path = Path(parquet_path)

    _validate_source_file(csv_path)

    if parquet_path.exists() and not overwrite:
        raise ParquetConversionError(
            f"Parquet destination already exists: {parquet_path}"
        )

    source_stat_before = csv_path.stat()
    source_checksum_before = calculate_sha256(csv_path)

    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = parquet_path.with_name(
        f"{parquet_path.name}.part"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    row_count = 0

    read_options = pacsv.ReadOptions(
        block_size=CSV_BLOCK_SIZE_BYTES,
        use_threads=True,
    )

    convert_options = pacsv.ConvertOptions(
        column_types=GOVERNED_ARROW_SCHEMA,
        include_columns=list(EXPECTED_CSV_HEADER),
        include_missing_columns=False,
    )

    try:
        reader = pacsv.open_csv(
            csv_path,
            read_options=read_options,
            convert_options=convert_options,
        )

        if not reader.schema.equals(
            GOVERNED_ARROW_SCHEMA,
            check_metadata=False,
        ):
            raise ParquetConversionError(
                "CSV reader schema does not match the governed Arrow schema.\n"
                f"Expected: {GOVERNED_ARROW_SCHEMA}\n"
                f"Actual:   {reader.schema}"
            )

        with pq.ParquetWriter(
            temporary_path,
            GOVERNED_ARROW_SCHEMA,
            compression=compression,
            write_statistics=True,
            store_schema=True,
        ) as writer:
            for batch in reader:
                if not batch.schema.equals(
                    GOVERNED_ARROW_SCHEMA,
                    check_metadata=False,
                ):
                    raise ParquetConversionError(
                        "A CSV record batch does not match "
                        "the governed Arrow schema"
                    )

                writer.write_batch(batch)
                row_count += batch.num_rows

        if (
            expected_row_count is not None
            and row_count != expected_row_count
        ):
            raise ParquetConversionError(
                "Converted row count does not match the expected count: "
                f"expected {expected_row_count}, received {row_count}"
            )

        validated_output = _validate_parquet_output(
            temporary_path,
            expected_row_count=row_count,
        )

        source_stat_after = csv_path.stat()
        source_checksum_after = calculate_sha256(csv_path)

        if (
            source_checksum_before != source_checksum_after
            or source_stat_before.st_size != source_stat_after.st_size
            or source_stat_before.st_mtime_ns
            != source_stat_after.st_mtime_ns
        ):
            raise ParquetConversionError(
                "The governed CSV source changed during conversion"
            )

        temporary_path.replace(parquet_path)

    except Exception as error:
        if temporary_path.exists():
            temporary_path.unlink()

        if isinstance(error, ParquetConversionError):
            raise

        raise ParquetConversionError(
            f"Unable to convert CSV to Parquet: {csv_path}"
        ) from error

    output_checksum = calculate_sha256(parquet_path)

    return {
        "source_path": str(csv_path.resolve()),
        "source_size_bytes": source_stat_before.st_size,
        "source_sha256": source_checksum_before,
        "source_modified": False,
        "parquet_path": str(parquet_path.resolve()),
        "parquet_size_bytes": parquet_path.stat().st_size,
        "parquet_sha256": output_checksum,
        "row_count": row_count,
        "column_count": validated_output["column_count"],
        "row_group_count": validated_output["row_group_count"],
        "parquet_format_version": validated_output["format_version"],
        "parquet_created_by": validated_output["created_by"],
        "schema": validated_output["schema"],
        "compression": compression,
        "expected_row_count": expected_row_count,
        "csv_block_size_bytes": CSV_BLOCK_SIZE_BYTES,
    }


def inspect_parquet_with_duckdb(
    parquet_path: Path,
) -> dict[str, Any]:
    """Inspect a Parquet dataset through an in-memory DuckDB connection."""

    parquet_path = Path(parquet_path)

    if not parquet_path.exists():
        raise ParquetConversionError(
            f"Parquet file does not exist: {parquet_path}"
        )

    if not parquet_path.is_file():
        raise ParquetConversionError(
            f"Parquet path is not a file: {parquet_path}"
        )

    resolved_path = str(parquet_path.resolve()).replace("'", "''")

    try:
        with duckdb.connect(database=":memory:") as connection:
            row_count_result = connection.execute(
                f"""
                SELECT COUNT(*)
                FROM read_parquet('{resolved_path}')
                """
            ).fetchone()

            if row_count_result is None:
                raise ParquetConversionError(
                    "DuckDB did not return a Parquet row count"
                )

            row_count = int(row_count_result[0])

            schema_rows = connection.execute(
                f"""
                DESCRIBE
                SELECT *
                FROM read_parquet('{resolved_path}')
                """
            ).fetchall()

    except ParquetConversionError:
        raise

    except duckdb.Error as error:
        raise ParquetConversionError(
            f"DuckDB could not read the Parquet file: {parquet_path}"
        ) from error

    columns = [
        {
            "name": str(row[0]),
            "duckdb_type": str(row[1]),
        }
        for row in schema_rows
    ]

    actual_column_names = tuple(
        column["name"] for column in columns
    )

    if actual_column_names != EXPECTED_DUCKDB_COLUMNS:
        raise ParquetConversionError(
            "DuckDB column names do not match the expected analytical schema.\n"
            f"Expected: {EXPECTED_DUCKDB_COLUMNS}\n"
            f"Actual:   {actual_column_names}"
        )

    return {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "database": ":memory:",
        "source": str(parquet_path.resolve()),
    }


def build_conversion_metadata(
    conversion_result: dict[str, Any],
    duckdb_inspection: dict[str, Any],
) -> dict[str, Any]:
    """Build reproducibility metadata for a verified conversion."""

    if (
        conversion_result["row_count"]
        != duckdb_inspection["row_count"]
    ):
        raise ParquetConversionError(
            "DuckDB row count does not match the conversion row count: "
            f"conversion={conversion_result['row_count']}, "
            f"duckdb={duckdb_inspection['row_count']}"
        )

    if (
        conversion_result["column_count"]
        != duckdb_inspection["column_count"]
    ):
        raise ParquetConversionError(
            "DuckDB column count does not match the conversion column count: "
            f"conversion={conversion_result['column_count']}, "
            f"duckdb={duckdb_inspection['column_count']}"
        )

    return {
        "metadata_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "processing_status": "converted_and_verified",
        "source": {
            "path": conversion_result["source_path"],
            "size_bytes": conversion_result["source_size_bytes"],
            "sha256": conversion_result["source_sha256"],
            "modified": conversion_result["source_modified"],
        },
        "output": {
            "path": conversion_result["parquet_path"],
            "size_bytes": conversion_result["parquet_size_bytes"],
            "sha256": conversion_result["parquet_sha256"],
            "row_count": conversion_result["row_count"],
            "column_count": conversion_result["column_count"],
            "row_group_count": conversion_result["row_group_count"],
            "parquet_format_version": (
                conversion_result["parquet_format_version"]
            ),
            "parquet_created_by": (
                conversion_result["parquet_created_by"]
            ),
        },
        "configuration": {
            "compression": conversion_result["compression"],
            "expected_row_count": (
                conversion_result["expected_row_count"]
            ),
            "csv_block_size_bytes": (
                conversion_result["csv_block_size_bytes"]
            ),
            "write_statistics": True,
            "store_arrow_schema": True,
        },
        "schema": {
            "column_count": conversion_result["column_count"],
            "columns": conversion_result["schema"],
            "unnamed_source_column_preserved": True,
            "duckdb_unnamed_column_alias": "C0",
        },
        "duckdb_validation": duckdb_inspection,
        "software": {
            "python_version": platform.python_version(),
            "pyarrow_version": pyarrow.__version__,
            "duckdb_version": duckdb.__version__,
        },
        "source_preservation": {
            "source_modified": False,
            "note": (
                "The governed CSV was opened for reading and "
                "was not rewritten."
            ),
        },
    }


def write_conversion_metadata(
    metadata: dict[str, Any],
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> Path:
    """Write conversion metadata atomically as formatted JSON."""

    metadata_path = Path(metadata_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = metadata_path.with_name(
        f"{metadata_path.name}.part"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            json.dump(metadata, handle, indent=2, sort_keys=True)
            handle.write("\n")

        temporary_path.replace(metadata_path)

    except OSError as error:
        if temporary_path.exists():
            temporary_path.unlink()

        raise ParquetConversionError(
            f"Unable to write conversion metadata: {metadata_path}"
        ) from error

    return metadata_path


def run_conversion_workflow(
    csv_path: Path = DATASET_CSV_PATH,
    parquet_path: Path = DEFAULT_PARQUET_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
    *,
    expected_row_count: int | None = VERIFIED_SOURCE_ROW_COUNT,
    compression: str = PARQUET_COMPRESSION,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run conversion, Parquet validation, DuckDB inspection, and metadata."""

    conversion_result = convert_csv_to_parquet(
        csv_path,
        parquet_path,
        expected_row_count=expected_row_count,
        compression=compression,
        overwrite=overwrite,
    )

    duckdb_inspection = inspect_parquet_with_duckdb(
        Path(conversion_result["parquet_path"])
    )

    metadata = build_conversion_metadata(
        conversion_result,
        duckdb_inspection,
    )

    completed_metadata_path = write_conversion_metadata(
        metadata,
        metadata_path,
    )

    return {
        "processing_status": "converted_and_verified",
        "parquet_path": conversion_result["parquet_path"],
        "metadata_path": str(completed_metadata_path.resolve()),
        "row_count": conversion_result["row_count"],
        "column_count": conversion_result["column_count"],
        "source_sha256": conversion_result["source_sha256"],
        "parquet_sha256": conversion_result["parquet_sha256"],
        "compression": conversion_result["compression"],
        "pyarrow_version": pyarrow.__version__,
        "duckdb_version": duckdb.__version__,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the command-line parser for the conversion workflow."""

    parser = argparse.ArgumentParser(
        description=(
            "Convert governed MetroPT-3 CSV data to validated Parquet "
            "and verify analytical access through DuckDB."
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DATASET_CSV_PATH,
        help="Governed CSV source path",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PARQUET_PATH,
        help="Parquet output path",
    )

    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA_PATH,
        help="Conversion metadata JSON path",
    )

    parser.add_argument(
        "--expected-row-count",
        type=int,
        default=VERIFIED_SOURCE_ROW_COUNT,
        help="Expected number of source data rows",
    )

    parser.add_argument(
        "--compression",
        default=PARQUET_COMPRESSION,
        help="Parquet compression codec",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing Parquet output",
    )

    return parser


def main() -> int:
    """Run the complete governed conversion workflow."""

    arguments = build_argument_parser().parse_args()

    try:
        result = run_conversion_workflow(
            csv_path=arguments.input,
            parquet_path=arguments.output,
            metadata_path=arguments.metadata,
            expected_row_count=arguments.expected_row_count,
            compression=arguments.compression,
            overwrite=arguments.overwrite,
        )
    except ParquetConversionError as error:
        print(f"ERROR: {error}")
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""Value-level and temporal data-quality profiling for governed CSV sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .acquire import DATASET_CSV_PATH, EXPECTED_CSV_HEADER
except ImportError:  # Supports direct execution from this source directory.
    from acquire import DATASET_CSV_PATH, EXPECTED_CSV_HEADER


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_PATH = (
    PROJECT_ROOT / "outputs" / "metropt3_data_quality_report.json"
)

TIMESTAMP_COLUMN = "timestamp"
NUMERIC_COLUMNS = tuple(
    column for column in EXPECTED_CSV_HEADER if column != TIMESTAMP_COLUMN
)
BINARY_COLUMNS = (
    "COMP",
    "DV_eletric",
    "Towers",
    "MPG",
    "LPS",
    "Pressure_switch",
    "Oil_level",
    "Caudal_impulses",
)
ALLOWED_BINARY_VALUES = (0.0, 1.0)
ROW_FINGERPRINT_SIZE = 32
DEFAULT_GAP_MULTIPLIER = 1.5
DEFAULT_MAX_GAP_DETAILS = 20
UNNAMED_COLUMN_REPORT_KEY = "__unnamed_column_0__"


class DataQualityError(RuntimeError):
    """Raised when a governed data-quality profile cannot be completed."""


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO-like timestamp and return a timezone-neutral datetime."""

    normalized = value.strip()

    if not normalized:
        raise ValueError("timestamp is empty")

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def _row_fingerprint(row: Iterable[str]) -> bytes:
    """Return a stable SHA-256 fingerprint for one exact CSV row."""

    digest = hashlib.sha256()

    for value in row:
        encoded = value.encode("utf-8", errors="surrogatepass")
        digest.update(len(encoded).to_bytes(8, byteorder="big"))
        digest.update(encoded)

    return digest.digest()


def _validate_input_file(csv_path: Path) -> None:
    """Validate that a local CSV input exists and is readable."""

    if not csv_path.exists():
        raise DataQualityError(f"CSV file does not exist: {csv_path}")

    if not csv_path.is_file():
        raise DataQualityError(f"CSV path is not a file: {csv_path}")

    if csv_path.stat().st_size == 0:
        raise DataQualityError(f"CSV file is empty: {csv_path}")


def _validate_header(
    header: tuple[str, ...],
    expected_header: tuple[str, ...] | None,
) -> None:
    """Validate required and governed CSV header conditions."""

    if TIMESTAMP_COLUMN not in header:
        raise DataQualityError(
            f"Required column {TIMESTAMP_COLUMN!r} is missing from the CSV header"
        )

    if expected_header is not None and header != expected_header:
        raise DataQualityError(
            "CSV header does not match the governed schema.\n"
            f"Expected: {expected_header}\n"
            f"Actual:   {header}"
        )


def _report_column_key(column: str) -> str:
    """Return a non-empty JSON property name for one source column."""

    return column if column else UNNAMED_COLUMN_REPORT_KEY


def _top_counter_items(counter: Counter[float], limit: int = 10) -> list[dict[str, Any]]:
    """Return the most frequent numeric counter values in JSON-ready form."""

    return [
        {"interval_seconds": value, "count": count}
        for value, count in sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
    ]


def profile_csv(
    csv_path: Path = DATASET_CSV_PATH,
    *,
    expected_header: tuple[str, ...] | None = EXPECTED_CSV_HEADER,
    numeric_columns: tuple[str, ...] = NUMERIC_COLUMNS,
    binary_columns: tuple[str, ...] = BINARY_COLUMNS,
    gap_multiplier: float = DEFAULT_GAP_MULTIPLIER,
    max_gap_details: int = DEFAULT_MAX_GAP_DETAILS,
) -> dict[str, Any]:
    """Profile one governed CSV without modifying the source file."""

    csv_path = Path(csv_path)
    _validate_input_file(csv_path)

    if gap_multiplier <= 1.0:
        raise ValueError("gap_multiplier must be greater than 1.0")

    if max_gap_details < 0:
        raise ValueError("max_gap_details cannot be negative")

    row_count = 0
    row_width_mismatch_count = 0
    duplicate_row_count = 0
    seen_row_fingerprints: set[bytes] = set()

    timestamp_parse_failure_count = 0
    timestamp_out_of_order_count = 0
    timestamp_duplicate_adjacent_count = 0
    nonpositive_interval_count = 0
    first_valid_timestamp: datetime | None = None
    last_valid_timestamp: datetime | None = None
    previous_valid_timestamp: datetime | None = None
    previous_valid_row_number: int | None = None
    interval_counts: Counter[float] = Counter()
    largest_intervals: list[tuple[float, int, str, str]] = []

    missing_counts: Counter[str] = Counter()
    numeric_coercion_failures: Counter[str] = Counter()
    non_finite_numeric_counts: Counter[str] = Counter()
    invalid_binary_counts: Counter[str] = Counter()
    invalid_binary_values: dict[str, Counter[str]] = {
        column: Counter() for column in binary_columns
    }

    try:
        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.reader(csv_file)
            raw_header = next(reader, None)

            if raw_header is None:
                raise DataQualityError(
                    f"CSV file does not contain a header: {csv_path}"
                )

            header = tuple(raw_header)
            _validate_header(header, expected_header)
            column_indexes = {
                column: index for index, column in enumerate(header)
            }

            missing_numeric_columns = sorted(
                set(numeric_columns) - set(header)
            )
            missing_binary_columns = sorted(
                set(binary_columns) - set(header)
            )

            if missing_numeric_columns:
                raise DataQualityError(
                    "Configured numeric columns are missing from the CSV header: "
                    + ", ".join(repr(column) for column in missing_numeric_columns)
                )

            if missing_binary_columns:
                raise DataQualityError(
                    "Configured binary columns are missing from the CSV header: "
                    + ", ".join(repr(column) for column in missing_binary_columns)
                )

            timestamp_index = column_indexes[TIMESTAMP_COLUMN]

            for source_row_number, raw_row in enumerate(reader, start=2):
                row_count += 1

                fingerprint = _row_fingerprint(raw_row)
                if fingerprint in seen_row_fingerprints:
                    duplicate_row_count += 1
                else:
                    seen_row_fingerprints.add(fingerprint)

                if len(raw_row) != len(header):
                    row_width_mismatch_count += 1

                row = list(raw_row[: len(header)])
                if len(row) < len(header):
                    row.extend([""] * (len(header) - len(row)))

                for column, index in column_indexes.items():
                    if not row[index].strip():
                        missing_counts[column] += 1

                timestamp_text = row[timestamp_index]
                try:
                    current_timestamp = _parse_timestamp(timestamp_text)
                except (ValueError, OverflowError):
                    timestamp_parse_failure_count += 1
                    current_timestamp = None

                if current_timestamp is not None:
                    if first_valid_timestamp is None:
                        first_valid_timestamp = current_timestamp

                    last_valid_timestamp = current_timestamp

                    if previous_valid_timestamp is not None:
                        interval_seconds = (
                            current_timestamp - previous_valid_timestamp
                        ).total_seconds()

                        if interval_seconds < 0:
                            timestamp_out_of_order_count += 1
                        elif interval_seconds == 0:
                            timestamp_duplicate_adjacent_count += 1
                            nonpositive_interval_count += 1
                        else:
                            interval_counts[interval_seconds] += 1

                            if max_gap_details > 0:
                                detail = (
                                    interval_seconds,
                                    source_row_number,
                                    previous_valid_timestamp.isoformat(sep=" "),
                                    current_timestamp.isoformat(sep=" "),
                                )

                                if len(largest_intervals) < max_gap_details:
                                    heapq.heappush(largest_intervals, detail)
                                elif detail > largest_intervals[0]:
                                    heapq.heapreplace(largest_intervals, detail)

                    previous_valid_timestamp = current_timestamp
                    previous_valid_row_number = source_row_number

                numeric_values: dict[str, float | None] = {}

                for column in numeric_columns:
                    value = row[column_indexes[column]].strip()

                    if not value:
                        numeric_values[column] = None
                        continue

                    try:
                        numeric_value = float(value)
                    except ValueError:
                        numeric_coercion_failures[column] += 1
                        numeric_values[column] = None
                        continue

                    numeric_values[column] = numeric_value

                    if not math.isfinite(numeric_value):
                        non_finite_numeric_counts[column] += 1

                for column in binary_columns:
                    raw_value = row[column_indexes[column]].strip()
                    numeric_value = numeric_values[column]

                    if not raw_value:
                        continue

                    if (
                        numeric_value is None
                        or not math.isfinite(numeric_value)
                        or numeric_value not in ALLOWED_BINARY_VALUES
                    ):
                        invalid_binary_counts[column] += 1
                        invalid_binary_values[column][raw_value] += 1

    except DataQualityError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise DataQualityError(
            f"Unable to profile CSV file: {csv_path}"
        ) from error

    expected_interval_seconds: float | None = None
    gap_threshold_seconds: float | None = None
    gap_count = 0
    largest_gap_seconds: float | None = None
    gap_details: list[dict[str, Any]] = []

    if interval_counts:
        expected_interval_seconds = min(
            interval_counts,
            key=lambda interval: (-interval_counts[interval], interval),
        )
        gap_threshold_seconds = expected_interval_seconds * gap_multiplier
        gap_count = sum(
            count
            for interval, count in interval_counts.items()
            if interval > gap_threshold_seconds
        )
        largest_gap_seconds = max(interval_counts)

        gap_details = [
            {
                "interval_seconds": interval,
                "current_source_row": row_number,
                "previous_timestamp": previous_timestamp,
                "current_timestamp": current_timestamp,
            }
            for (
                interval,
                row_number,
                previous_timestamp,
                current_timestamp,
            ) in sorted(largest_intervals, reverse=True)
            if interval > gap_threshold_seconds
        ]

    total_missing_values = sum(missing_counts.values())
    duplicate_percentage = (
        (duplicate_row_count / row_count) * 100.0 if row_count else 0.0
    )

    return {
        "profile_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_preservation": {
            "source_modified": False,
            "note": "The profiler opens the source CSV in read-only mode and does not rewrite it.",
        },
        "source_file": {
            "path": str(csv_path.resolve()),
            "size_bytes": csv_path.stat().st_size,
        },
        "schema": {
            "columns": list(header),
            "report_column_keys": [
                _report_column_key(column) for column in header
            ],
            "unnamed_column_report_key": UNNAMED_COLUMN_REPORT_KEY,
            "column_count": len(header),
            "row_width_mismatch_count": row_width_mismatch_count,
        },
        "rows": {
            "data_row_count": row_count,
            "duplicate_row_count": duplicate_row_count,
            "duplicate_percentage": round(duplicate_percentage, 6),
            "duplicate_detection_method": "SHA-256 fingerprint of each exact CSV row",
        },
        "timestamps": {
            "column": TIMESTAMP_COLUMN,
            "first_valid_timestamp": (
                first_valid_timestamp.isoformat(sep=" ")
                if first_valid_timestamp is not None
                else None
            ),
            "last_valid_timestamp": (
                last_valid_timestamp.isoformat(sep=" ")
                if last_valid_timestamp is not None
                else None
            ),
            "parse_failure_count": timestamp_parse_failure_count,
            "out_of_order_count": timestamp_out_of_order_count,
            "adjacent_duplicate_count": timestamp_duplicate_adjacent_count,
            "nonpositive_interval_count": nonpositive_interval_count,
            "monotonic_non_decreasing": timestamp_out_of_order_count == 0,
            "expected_interval_seconds": expected_interval_seconds,
            "gap_multiplier": gap_multiplier,
            "gap_threshold_seconds": gap_threshold_seconds,
            "gap_count": gap_count,
            "largest_gap_seconds": largest_gap_seconds,
            "top_interval_frequencies": _top_counter_items(interval_counts),
            "largest_gap_details": gap_details,
        },
        "missing_values": {
            "total_missing_value_count": total_missing_values,
            "by_column": {
                _report_column_key(column): missing_counts[column]
                for column in header
            },
        },
        "numeric_validation": {
            "checked_columns": list(numeric_columns),
            "coercion_failure_count_by_column": {
                _report_column_key(column): numeric_coercion_failures[column]
                for column in numeric_columns
            },
            "non_finite_value_count_by_column": {
                _report_column_key(column): non_finite_numeric_counts[column]
                for column in numeric_columns
            },
        },
        "binary_validation": {
            "checked_columns": list(binary_columns),
            "allowed_values": [0, 1],
            "invalid_value_count_by_column": {
                column: invalid_binary_counts[column]
                for column in binary_columns
            },
            "invalid_values_by_column": {
                column: dict(
                    sorted(
                        invalid_binary_values[column].items(),
                        key=lambda item: (-item[1], item[0]),
                    )
                )
                for column in binary_columns
            },
        },
    }


def write_json_report(
    report: dict[str, Any],
    report_path: Path = DEFAULT_REPORT_PATH,
) -> Path:
    """Write a JSON report atomically and return its completed path."""

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = report_path.with_name(f"{report_path.name}.part")

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")

        temporary_path.replace(report_path)
    except OSError as error:
        if temporary_path.exists():
            temporary_path.unlink()
        raise DataQualityError(
            f"Unable to write data-quality report: {report_path}"
        ) from error

    return report_path


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the command-line parser for the profiling utility."""

    parser = argparse.ArgumentParser(
        description=(
            "Profile governed MetroPT-3 CSV data without modifying the raw source."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DATASET_CSV_PATH,
        help="CSV file to profile (default: governed MetroPT-3 raw CSV)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="JSON report destination",
    )
    parser.add_argument(
        "--gap-multiplier",
        type=float,
        default=DEFAULT_GAP_MULTIPLIER,
        help="Mark intervals larger than expected_interval × this value as gaps",
    )
    parser.add_argument(
        "--max-gap-details",
        type=int,
        default=DEFAULT_MAX_GAP_DETAILS,
        help="Maximum number of largest gap records to include",
    )
    return parser


def main() -> int:
    """Run the profiler from the command line."""

    arguments = build_argument_parser().parse_args()

    try:
        report = profile_csv(
            csv_path=arguments.input,
            gap_multiplier=arguments.gap_multiplier,
            max_gap_details=arguments.max_gap_details,
        )
        report_path = write_json_report(report, arguments.output)
    except (DataQualityError, ValueError) as error:
        print(f"Data-quality profiling failed: {error}")
        return 1

    print("Data-quality profiling completed successfully.")
    print(f"Rows profiled: {report['rows']['data_row_count']}")
    print(
        "Timestamp parse failures: "
        f"{report['timestamps']['parse_failure_count']}"
    )
    print(
        "Out-of-order timestamps: "
        f"{report['timestamps']['out_of_order_count']}"
    )
    print(f"Detected gaps: {report['timestamps']['gap_count']}")
    print(f"Duplicate rows: {report['rows']['duplicate_row_count']}")
    print(f"Report: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

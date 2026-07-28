"""Reproducible exploratory analysis for the verified MetroPT-3 Parquet data."""

from __future__ import annotations

import argparse
import csv
import json
import platform
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

import duckdb

try:
    from predictive_maintenance.data.acquire import calculate_sha256
    from predictive_maintenance.data.data_quality import BINARY_COLUMNS
    from predictive_maintenance.data.parquet_conversion import (
        DEFAULT_PARQUET_PATH,
        EXPECTED_DUCKDB_COLUMNS,
    )
except ModuleNotFoundError:  # Supports direct execution from this source file.
    import sys

    source_directory = Path(__file__).resolve().parents[2]
    if str(source_directory) not in sys.path:
        sys.path.insert(0, str(source_directory))

    from predictive_maintenance.data.acquire import calculate_sha256
    from predictive_maintenance.data.data_quality import BINARY_COLUMNS
    from predictive_maintenance.data.parquet_conversion import (
        DEFAULT_PARQUET_PATH,
        EXPECTED_DUCKDB_COLUMNS,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "eda"
DEFAULT_GAP_THRESHOLD_SECONDS = 15.0
DEFAULT_MAX_GAP_DETAILS = 20
ANALYSIS_SCHEMA_VERSION = 1

SIGNAL_COLUMNS = (
    "TP2",
    "TP3",
    "H1",
    "DV_pressure",
    "Reservoirs",
    "Oil_temperature",
    "Motor_current",
)

SUMMARY_FILENAME = "metropt3_eda_summary.json"
SIGNAL_SUMMARY_FILENAME = "signal_summary.csv"
OPERATING_STATE_FILENAME = "operating_state_frequencies.csv"
TEMPORAL_SEGMENT_FILENAME = "temporal_segments.csv"
TEMPORAL_GAP_FILENAME = "temporal_gaps.csv"
OPERATING_STATE_FIGURE_FILENAME = "operating_state_frequencies.svg"
SIGNAL_DISTRIBUTION_FIGURE_FILENAME = "signal_distribution_overview.svg"


class EDAError(RuntimeError):
    """Raised when governed exploratory analysis cannot be completed."""


def _validate_parquet_input(parquet_path: Path) -> None:
    """Validate that the analytical Parquet input exists and is readable."""

    if not parquet_path.exists():
        raise EDAError(f"Parquet dataset does not exist: {parquet_path}")

    if not parquet_path.is_file():
        raise EDAError(f"Parquet dataset path is not a file: {parquet_path}")

    if parquet_path.stat().st_size == 0:
        raise EDAError(f"Parquet dataset is empty: {parquet_path}")


def _sql_path_literal(path: Path) -> str:
    """Return a safely escaped SQL string literal for one local path."""

    return str(path.resolve()).replace("'", "''")


def _json_value(value: Any) -> Any:
    """Convert DuckDB values into deterministic JSON-compatible values."""

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, tuple):
        return [_json_value(item) for item in value]

    if isinstance(value, list):
        return [_json_value(item) for item in value]

    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}

    return value


def _write_json_atomic(payload: dict[str, Any], output_path: Path) -> Path:
    """Write one JSON artifact through a temporary file and atomic replace."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.part")

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                _json_value(payload),
                handle,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")

        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    return output_path


def _write_csv_atomic(
    rows: Iterable[dict[str, Any]],
    fieldnames: tuple[str, ...],
    output_path: Path,
) -> Path:
    """Write one CSV artifact through a temporary file and atomic replace."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.part")

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                lineterminator="\n",
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {field: _json_value(row.get(field)) for field in fieldnames}
                )

        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    return output_path


def _write_text_atomic(text: str, output_path: Path) -> Path:
    """Write one UTF-8 text artifact through an atomic replace."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.part")

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        temporary_path.write_text(text, encoding="utf-8", newline="\n")
        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    return output_path


def _output_paths(output_dir: Path) -> dict[str, Path]:
    """Return the governed output paths for one EDA execution."""

    figures_dir = output_dir / "figures"
    return {
        "summary": output_dir / SUMMARY_FILENAME,
        "signal_summary": output_dir / SIGNAL_SUMMARY_FILENAME,
        "operating_states": output_dir / OPERATING_STATE_FILENAME,
        "temporal_segments": output_dir / TEMPORAL_SEGMENT_FILENAME,
        "temporal_gaps": output_dir / TEMPORAL_GAP_FILENAME,
        "operating_state_figure": figures_dir
        / OPERATING_STATE_FIGURE_FILENAME,
        "signal_distribution_figure": figures_dir
        / SIGNAL_DISTRIBUTION_FIGURE_FILENAME,
    }


def _protect_existing_outputs(
    output_paths: dict[str, Path],
    *,
    overwrite: bool,
) -> None:
    """Refuse silent replacement of existing analytical artifacts."""

    existing = [path for path in output_paths.values() if path.exists()]

    if existing and not overwrite:
        formatted = "\n".join(f"- {path}" for path in existing)
        raise EDAError(
            "EDA output already exists. Use --overwrite only after reviewing "
            f"the current artifacts:\n{formatted}"
        )


def _validate_schema(connection: duckdb.DuckDBPyConnection) -> list[dict[str, str]]:
    """Validate the expected analytical column names and return schema records."""

    schema_rows = connection.execute("DESCRIBE SELECT * FROM metropt3").fetchall()
    columns = [
        {
            "name": str(row[0]),
            "duckdb_type": str(row[1]),
        }
        for row in schema_rows
    ]
    actual_names = tuple(column["name"] for column in columns)

    if actual_names != EXPECTED_DUCKDB_COLUMNS:
        raise EDAError(
            "DuckDB columns do not match the verified analytical schema.\n"
            f"Expected: {EXPECTED_DUCKDB_COLUMNS}\n"
            f"Actual:   {actual_names}"
        )

    return columns


def _timestamp_coverage(
    connection: duckdb.DuckDBPyConnection,
) -> dict[str, Any]:
    """Measure row count and timestamp coverage."""

    row = connection.execute(
        """
        SELECT
            COUNT(*) AS row_count,
            MIN(timestamp) AS first_timestamp,
            MAX(timestamp) AS last_timestamp,
            date_diff(
                'second',
                MIN(timestamp),
                MAX(timestamp)
            ) AS elapsed_seconds,
            COUNT(DISTINCT CAST(timestamp AS DATE)) AS observed_calendar_days
        FROM metropt3
        """
    ).fetchone()

    if row is None:
        raise EDAError("DuckDB did not return timestamp coverage results")

    elapsed_seconds = int(row[3]) if row[3] is not None else 0
    return {
        "row_count": int(row[0]),
        "first_timestamp": row[1],
        "last_timestamp": row[2],
        "elapsed_seconds": elapsed_seconds,
        "elapsed_hours": elapsed_seconds / 3600.0,
        "observed_calendar_days": int(row[4]),
    }


def _signal_summaries(
    connection: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    """Calculate descriptive statistics for governed continuous signals."""

    summaries: list[dict[str, Any]] = []

    for signal in SIGNAL_COLUMNS:
        row = connection.execute(
            f"""
            SELECT
                COUNT({signal}) AS non_null_count,
                MIN({signal}) AS minimum,
                quantile_cont({signal}, 0.01) AS q01,
                quantile_cont({signal}, 0.25) AS q25,
                quantile_cont({signal}, 0.50) AS median,
                AVG({signal}) AS mean,
                quantile_cont({signal}, 0.75) AS q75,
                quantile_cont({signal}, 0.99) AS q99,
                MAX({signal}) AS maximum,
                stddev_pop({signal}) AS standard_deviation
            FROM metropt3
            """
        ).fetchone()

        if row is None:
            raise EDAError(f"DuckDB did not return a summary for {signal}")

        summaries.append(
            {
                "signal": signal,
                "non_null_count": int(row[0]),
                "minimum": float(row[1]),
                "q01": float(row[2]),
                "q25": float(row[3]),
                "median": float(row[4]),
                "mean": float(row[5]),
                "q75": float(row[6]),
                "q99": float(row[7]),
                "maximum": float(row[8]),
                "standard_deviation": float(row[9]),
            }
        )

    return summaries


def _operating_state_frequencies(
    connection: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    """Calculate zero/one frequencies for governed binary operating signals."""

    rows: list[dict[str, Any]] = []

    for signal in BINARY_COLUMNS:
        results = connection.execute(
            f"""
            SELECT
                CAST({signal} AS INTEGER) AS state,
                COUNT(*) AS row_count
            FROM metropt3
            GROUP BY state
            ORDER BY state
            """
        ).fetchall()
        total = sum(int(result[1]) for result in results)

        if total == 0:
            raise EDAError(f"Operating-state query returned no rows for {signal}")

        for state, row_count in results:
            count = int(row_count)
            rows.append(
                {
                    "signal": signal,
                    "state": int(state),
                    "row_count": count,
                    "percentage": count * 100.0 / total,
                }
            )

    return rows


def _temporal_segments(
    connection: duckdb.DuckDBPyConnection,
    *,
    gap_threshold_seconds: float,
) -> list[dict[str, Any]]:
    """Create observation segments that do not cross documented temporal gaps."""

    results = connection.execute(
        """
        WITH ordered AS (
            SELECT
                timestamp,
                LAG(timestamp) OVER (ORDER BY timestamp) AS previous_timestamp
            FROM metropt3
        ),
        marked AS (
            SELECT
                timestamp,
                CASE
                    WHEN previous_timestamp IS NULL THEN 1
                    WHEN date_diff(
                        'second',
                        previous_timestamp,
                        timestamp
                    ) > ? THEN 1
                    ELSE 0
                END AS starts_new_segment
            FROM ordered
        ),
        segmented AS (
            SELECT
                timestamp,
                SUM(starts_new_segment) OVER (
                    ORDER BY timestamp
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS segment_id
            FROM marked
        )
        SELECT
            CAST(segment_id AS BIGINT) AS segment_id,
            MIN(timestamp) AS start_timestamp,
            MAX(timestamp) AS end_timestamp,
            COUNT(*) AS row_count,
            date_diff(
                'second',
                MIN(timestamp),
                MAX(timestamp)
            ) AS span_seconds
        FROM segmented
        GROUP BY segment_id
        ORDER BY segment_id
        """,
        [gap_threshold_seconds],
    ).fetchall()

    return [
        {
            "segment_id": int(row[0]),
            "start_timestamp": row[1],
            "end_timestamp": row[2],
            "row_count": int(row[3]),
            "span_seconds": int(row[4]),
            "span_hours": int(row[4]) / 3600.0,
        }
        for row in results
    ]


def _temporal_gaps(
    connection: duckdb.DuckDBPyConnection,
    *,
    gap_threshold_seconds: float,
    max_gap_details: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Count temporal gaps and return the largest governed details."""

    base_query = """
        WITH ordered AS (
            SELECT
                timestamp AS next_timestamp,
                LAG(timestamp) OVER (ORDER BY timestamp) AS previous_timestamp
            FROM metropt3
        )
        SELECT
            previous_timestamp,
            next_timestamp,
            date_diff(
                'second',
                previous_timestamp,
                next_timestamp
            ) AS gap_seconds
        FROM ordered
        WHERE previous_timestamp IS NOT NULL
          AND date_diff(
                'second',
                previous_timestamp,
                next_timestamp
              ) > ?
    """

    count_row = connection.execute(
        f"SELECT COUNT(*) FROM ({base_query}) AS gaps",
        [gap_threshold_seconds],
    ).fetchone()

    if count_row is None:
        raise EDAError("DuckDB did not return a temporal-gap count")

    details = connection.execute(
        f"""
        {base_query}
        ORDER BY gap_seconds DESC, next_timestamp
        LIMIT ?
        """,
        [gap_threshold_seconds, max_gap_details],
    ).fetchall()

    return int(count_row[0]), [
        {
            "previous_timestamp": row[0],
            "next_timestamp": row[1],
            "gap_seconds": int(row[2]),
            "gap_hours": int(row[2]) / 3600.0,
        }
        for row in details
    ]


def _svg_document(width: int, height: int, body: str) -> str:
    """Return one complete, accessible SVG document."""

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        'role="img">\n'
        f"{body}\n"
        "</svg>\n"
    )


def _operating_state_svg(rows: list[dict[str, Any]]) -> str:
    """Build an SVG bar chart of active-state percentages."""

    active = {
        str(row["signal"]): float(row["percentage"])
        for row in rows
        if int(row["state"]) == 1
    }
    signals = list(BINARY_COLUMNS)
    width = 920
    height = 150 + len(signals) * 54
    chart_left = 220
    chart_width = 620
    body = [
        "<title>MetroPT-3 operating-state active percentages</title>",
        "<desc>Percentage of rows where each governed binary signal equals one.</desc>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="40" y="48" font-size="26" font-family="Arial" '
        'font-weight="700">Operating-State Active Frequency</text>',
        '<text x="40" y="78" font-size="15" font-family="Arial">'
        "Percentage of rows with state = 1</text>",
    ]

    for tick in range(0, 101, 20):
        x = chart_left + chart_width * tick / 100.0
        body.append(
            f'<line x1="{x:.1f}" y1="105" x2="{x:.1f}" '
            f'y2="{height - 40}" stroke="#d9d9d9" stroke-width="1"/>'
        )
        body.append(
            f'<text x="{x:.1f}" y="100" text-anchor="middle" '
            f'font-size="12" font-family="Arial">{tick}%</text>'
        )

    for index, signal in enumerate(signals):
        percentage = active.get(signal, 0.0)
        y = 125 + index * 54
        bar_width = chart_width * percentage / 100.0
        body.append(
            f'<text x="{chart_left - 12}" y="{y + 20}" '
            'text-anchor="end" font-size="14" font-family="Arial">'
            f"{escape(signal)}</text>"
        )
        body.append(
            f'<rect x="{chart_left}" y="{y}" width="{bar_width:.1f}" '
            'height="28" rx="4" fill="#315b7d"/>'
        )
        body.append(
            f'<text x="{min(chart_left + bar_width + 8, width - 58):.1f}" '
            f'y="{y + 20}" font-size="13" font-family="Arial">'
            f"{percentage:.2f}%</text>"
        )

    body.append(
        f'<text x="40" y="{height - 15}" font-size="12" '
        'font-family="Arial">Generated from the verified Parquet dataset; '
        "state frequencies are descriptive, not failure labels.</text>"
    )
    return _svg_document(width, height, "\n".join(body))


def _signal_distribution_svg(rows: list[dict[str, Any]]) -> str:
    """Build a per-signal normalized five-number distribution overview."""

    width = 1040
    height = 170 + len(rows) * 72
    chart_left = 230
    chart_width = 650
    body = [
        "<title>MetroPT-3 signal distribution overview</title>",
        "<desc>Each signal is normalized independently from its minimum to maximum.</desc>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="40" y="48" font-size="26" font-family="Arial" '
        'font-weight="700">Signal Distribution Overview</text>',
        '<text x="40" y="78" font-size="15" font-family="Arial">'
        "Each row uses its own minimum-to-maximum scale; box = Q25-Q75</text>",
        '<line x1="230" y1="112" x2="880" y2="112" '
        'stroke="#333333" stroke-width="1"/>',
        '<text x="230" y="103" font-size="12" font-family="Arial">Min</text>',
        '<text x="880" y="103" text-anchor="end" font-size="12" '
        'font-family="Arial">Max</text>',
    ]

    for index, row in enumerate(rows):
        y = 142 + index * 72
        minimum = float(row["minimum"])
        maximum = float(row["maximum"])
        span = maximum - minimum

        def scaled(value: float) -> float:
            if span == 0:
                return chart_left + chart_width / 2.0
            return chart_left + chart_width * (value - minimum) / span

        q25_x = scaled(float(row["q25"]))
        median_x = scaled(float(row["median"]))
        q75_x = scaled(float(row["q75"]))

        body.append(
            f'<text x="{chart_left - 16}" y="{y + 7}" '
            'text-anchor="end" font-size="15" font-family="Arial">'
            f'{escape(str(row["signal"]))}</text>'
        )
        body.append(
            f'<line x1="{chart_left}" y1="{y}" '
            f'x2="{chart_left + chart_width}" y2="{y}" '
            'stroke="#555555" stroke-width="2"/>'
        )
        body.append(
            f'<rect x="{q25_x:.1f}" y="{y - 12}" '
            f'width="{max(q75_x - q25_x, 1.0):.1f}" height="24" '
            'fill="#d9e7f2" stroke="#315b7d" stroke-width="2"/>'
        )
        body.append(
            f'<line x1="{median_x:.1f}" y1="{y - 16}" '
            f'x2="{median_x:.1f}" y2="{y + 16}" '
            'stroke="#111111" stroke-width="3"/>'
        )
        body.append(
            f'<text x="{chart_left}" y="{y + 30}" font-size="11" '
            f'font-family="Arial">{minimum:.4g}</text>'
        )
        body.append(
            f'<text x="{chart_left + chart_width}" y="{y + 30}" '
            'text-anchor="end" font-size="11" font-family="Arial">'
            f"{maximum:.4g}</text>"
        )

    body.append(
        f'<text x="40" y="{height - 18}" font-size="12" '
        'font-family="Arial">This figure describes observed values only and '
        "does not define anomalies or operating limits.</text>"
    )
    return _svg_document(width, height, "\n".join(body))


def run_eda_workflow(
    parquet_path: Path = DEFAULT_PARQUET_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    gap_threshold_seconds: float = DEFAULT_GAP_THRESHOLD_SECONDS,
    max_gap_details: int = DEFAULT_MAX_GAP_DETAILS,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run governed EDA and write reproducible analytical artifacts."""

    parquet_path = Path(parquet_path)
    output_dir = Path(output_dir)

    if gap_threshold_seconds <= 0:
        raise ValueError("gap_threshold_seconds must be greater than zero")

    if max_gap_details < 0:
        raise ValueError("max_gap_details cannot be negative")

    _validate_parquet_input(parquet_path)
    output_paths = _output_paths(output_dir)
    _protect_existing_outputs(output_paths, overwrite=overwrite)

    resolved_path = _sql_path_literal(parquet_path)

    try:
        with duckdb.connect(database=":memory:") as connection:
            connection.execute(
                f"""
                CREATE TEMP VIEW metropt3 AS
                SELECT *
                FROM read_parquet('{resolved_path}')
                """
            )

            schema = _validate_schema(connection)
            coverage = _timestamp_coverage(connection)
            signal_summaries = _signal_summaries(connection)
            operating_states = _operating_state_frequencies(connection)
            temporal_segments = _temporal_segments(
                connection,
                gap_threshold_seconds=gap_threshold_seconds,
            )
            gap_count, temporal_gaps = _temporal_gaps(
                connection,
                gap_threshold_seconds=gap_threshold_seconds,
                max_gap_details=max_gap_details,
            )
    except EDAError:
        raise
    except duckdb.Error as error:
        raise EDAError(
            f"DuckDB could not complete EDA for: {parquet_path}"
        ) from error

    if not temporal_segments:
        raise EDAError("Temporal segmentation returned no observation windows")

    if sum(segment["row_count"] for segment in temporal_segments) != coverage[
        "row_count"
    ]:
        raise EDAError(
            "Temporal segment row counts do not equal the dataset row count"
        )

    expected_segment_count = gap_count + 1 if coverage["row_count"] else 0
    if len(temporal_segments) != expected_segment_count:
        raise EDAError(
            "Temporal segment count does not equal gap count plus one: "
            f"segments={len(temporal_segments)}, gaps={gap_count}"
        )

    _write_csv_atomic(
        signal_summaries,
        (
            "signal",
            "non_null_count",
            "minimum",
            "q01",
            "q25",
            "median",
            "mean",
            "q75",
            "q99",
            "maximum",
            "standard_deviation",
        ),
        output_paths["signal_summary"],
    )
    _write_csv_atomic(
        operating_states,
        ("signal", "state", "row_count", "percentage"),
        output_paths["operating_states"],
    )
    _write_csv_atomic(
        temporal_segments,
        (
            "segment_id",
            "start_timestamp",
            "end_timestamp",
            "row_count",
            "span_seconds",
            "span_hours",
        ),
        output_paths["temporal_segments"],
    )
    _write_csv_atomic(
        temporal_gaps,
        (
            "previous_timestamp",
            "next_timestamp",
            "gap_seconds",
            "gap_hours",
        ),
        output_paths["temporal_gaps"],
    )
    _write_text_atomic(
        _operating_state_svg(operating_states),
        output_paths["operating_state_figure"],
    )
    _write_text_atomic(
        _signal_distribution_svg(signal_summaries),
        output_paths["signal_distribution_figure"],
    )

    summary: dict[str, Any] = {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "processing_status": "eda_completed",
        "input": {
            "path": str(parquet_path.resolve()),
            "size_bytes": parquet_path.stat().st_size,
            "sha256": calculate_sha256(parquet_path),
        },
        "configuration": {
            "gap_threshold_seconds": gap_threshold_seconds,
            "max_gap_details": max_gap_details,
            "database": ":memory:",
            "signal_columns": list(SIGNAL_COLUMNS),
            "binary_columns": list(BINARY_COLUMNS),
        },
        "schema": {
            "column_count": len(schema),
            "columns": schema,
        },
        "timestamp_coverage": coverage,
        "signal_summaries": signal_summaries,
        "operating_state_frequencies": operating_states,
        "temporal_analysis": {
            "gap_count": gap_count,
            "reported_gap_detail_count": len(temporal_gaps),
            "largest_reported_gaps": temporal_gaps,
            "segment_count": len(temporal_segments),
            "segments": temporal_segments,
            "continuity_rule": (
                "Rows separated by more than the configured gap threshold "
                "belong to different observation segments."
            ),
        },
        "scope_limits": [
            "Descriptive EDA only; no anomaly or failure labels are defined.",
            "No model features, training partitions, or predictive models are created.",
            "Observed values are not interpreted as equipment operating limits.",
        ],
        "outputs": {
            key: str(path.resolve()) for key, path in output_paths.items()
        },
        "software": {
            "python": platform.python_version(),
            "duckdb": duckdb.__version__,
        },
    }

    _write_json_atomic(summary, output_paths["summary"])
    return _json_value(summary)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for reproducible EDA."""

    parser = argparse.ArgumentParser(
        description=(
            "Run reproducible exploratory analysis over the verified "
            "MetroPT-3 Parquet dataset."
        )
    )
    parser.add_argument(
        "--parquet",
        type=Path,
        default=DEFAULT_PARQUET_PATH,
        help=f"Parquet input path (default: {DEFAULT_PARQUET_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"EDA output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--gap-threshold-seconds",
        type=float,
        default=DEFAULT_GAP_THRESHOLD_SECONDS,
        help=(
            "Start a new observation segment when the interval exceeds "
            f"this value (default: {DEFAULT_GAP_THRESHOLD_SECONDS})."
        ),
    )
    parser.add_argument(
        "--max-gap-details",
        type=int,
        default=DEFAULT_MAX_GAP_DETAILS,
        help=(
            "Maximum number of largest gap records to include "
            f"(default: {DEFAULT_MAX_GAP_DETAILS})."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the governed EDA output set after review.",
    )
    return parser


def main() -> int:
    """Run the command-line workflow with actionable terminal output."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        result = run_eda_workflow(
            parquet_path=arguments.parquet,
            output_dir=arguments.output_dir,
            gap_threshold_seconds=arguments.gap_threshold_seconds,
            max_gap_details=arguments.max_gap_details,
            overwrite=arguments.overwrite,
        )
    except (EDAError, OSError, ValueError) as error:
        parser.exit(status=1, message=f"EDA failed: {error}\n")

    temporal = result["temporal_analysis"]
    print("EDA completed and verified.")
    print(f"Rows analyzed: {result['timestamp_coverage']['row_count']}")
    print(f"Temporal gaps: {temporal['gap_count']}")
    print(f"Observation segments: {temporal['segment_count']}")
    print(f"Summary: {result['outputs']['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Materialize governed MetroPT-3 row-level target states.

The output is an auditable state table, not a model-ready binary target. Rows
outside documented failure intervals remain unverified unless an explicit
exclusion rule applies. The implementation does not engineer predictive
features, train models, or report performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from predictive_maintenance.analysis.target_definition import (
    ISO_FORMAT,
    Interval,
    TargetDefinitionError,
    parse_timestamp,
    validate_specification,
)


class TargetMaterializationError(ValueError):
    """Raised when governed row-level target states cannot be materialized."""


@dataclass(frozen=True)
class MaterializationPolicy:
    """Validated controls used to assign row-level states."""

    timestamp_column: str
    expected_sampling_seconds: float
    gap_threshold_seconds: float
    pre_event_exclusion_hours: float
    warning_horizon_hours: float | None
    states: dict[str, str]


def _required_nonempty_string(payload: dict[str, Any], key: str, prefix: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TargetMaterializationError(f"{prefix}.{key} must be a non-empty string.")
    return value.strip()


def _positive_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise TargetMaterializationError(f"{field_name} must be positive.")
    return float(value)


def validate_materialization_policy(payload: dict[str, Any]) -> MaterializationPolicy:
    """Validate and normalize the governed materialization policy."""
    policy = payload.get("materialization")
    if not isinstance(policy, dict):
        raise TargetMaterializationError("materialization must be an object.")

    timestamp_column = _required_nonempty_string(
        policy, "timestamp_column", "materialization"
    )
    expected_sampling_seconds = _positive_number(
        policy.get("expected_sampling_seconds"),
        "materialization.expected_sampling_seconds",
    )
    gap_threshold_seconds = _positive_number(
        policy.get("gap_threshold_seconds"),
        "materialization.gap_threshold_seconds",
    )
    if gap_threshold_seconds <= expected_sampling_seconds:
        raise TargetMaterializationError(
            "materialization.gap_threshold_seconds must exceed "
            "expected_sampling_seconds."
        )

    pre_event_exclusion_hours = _positive_number(
        policy.get("pre_event_exclusion_hours"),
        "materialization.pre_event_exclusion_hours",
    )

    warning_horizon = policy.get("warning_horizon_hours")
    if warning_horizon is not None:
        warning_horizon = _positive_number(
            warning_horizon, "materialization.warning_horizon_hours"
        )
        if warning_horizon <= pre_event_exclusion_hours:
            raise TargetMaterializationError(
                "materialization.warning_horizon_hours must exceed "
                "pre_event_exclusion_hours."
            )

    if policy.get("cross_segment_assignment_allowed") is not False:
        raise TargetMaterializationError(
            "materialization.cross_segment_assignment_allowed must be false."
        )
    if policy.get("unverified_rows_are_negative") is not False:
        raise TargetMaterializationError(
            "materialization.unverified_rows_are_negative must be false."
        )
    if policy.get("source_conflicts_create_labels") is not False:
        raise TargetMaterializationError(
            "materialization.source_conflicts_create_labels must be false."
        )

    states = policy.get("states")
    if not isinstance(states, dict):
        raise TargetMaterializationError("materialization.states must be an object.")
    required_states = (
        "documented_failure",
        "warning",
        "pre_event_exclusion",
        "partition_buffer_exclusion",
        "unverified",
    )
    normalized_states: dict[str, str] = {}
    for key in required_states:
        normalized_states[key] = _required_nonempty_string(
            states, key, "materialization.states"
        )
    if len(set(normalized_states.values())) != len(normalized_states):
        raise TargetMaterializationError(
            "materialization.states values must be unique."
        )

    return MaterializationPolicy(
        timestamp_column=timestamp_column,
        expected_sampling_seconds=expected_sampling_seconds,
        gap_threshold_seconds=gap_threshold_seconds,
        pre_event_exclusion_hours=pre_event_exclusion_hours,
        warning_horizon_hours=warning_horizon,
        states=normalized_states,
    )


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_specification(path: Path) -> dict[str, Any]:
    """Load a governed JSON specification as an object."""
    if not path.exists():
        raise TargetMaterializationError(f"Specification does not exist: {path}")
    if not path.is_file():
        raise TargetMaterializationError(f"Specification path is not a file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TargetMaterializationError(f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TargetMaterializationError(
            "The top-level specification value must be an object."
        )
    return payload


def _event_intervals(specification: dict[str, Any]) -> list[Interval]:
    intervals: list[Interval] = []
    for event in specification["events"]:
        intervals.append(
            Interval(
                start=parse_timestamp(event["start"], f"events.{event['name']}.start"),
                end=parse_timestamp(event["end"], f"events.{event['name']}.end"),
                name=event["name"],
            )
        )
    return intervals


def _table_columns(connection: duckdb.DuckDBPyConnection, parquet_path: Path) -> list[str]:
    rows = connection.execute(
        f"DESCRIBE SELECT * FROM read_parquet({_quote_literal(parquet_path)})"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _validate_input(
    connection: duckdb.DuckDBPyConnection,
    parquet_path: Path,
    specification: dict[str, Any],
    policy: MaterializationPolicy,
) -> dict[str, Any]:
    if not parquet_path.exists():
        raise TargetMaterializationError(f"Input Parquet does not exist: {parquet_path}")
    if not parquet_path.is_file():
        raise TargetMaterializationError(f"Input Parquet path is not a file: {parquet_path}")

    expected_checksum = specification["dataset"]["parquet_sha256"].lower()
    actual_checksum = _sha256(parquet_path)
    if actual_checksum != expected_checksum:
        raise TargetMaterializationError(
            "Input Parquet SHA-256 does not match the governed specification: "
            f"expected {expected_checksum}, got {actual_checksum}."
        )

    columns = _table_columns(connection, parquet_path)
    if policy.timestamp_column not in columns:
        raise TargetMaterializationError(
            f"Timestamp column {policy.timestamp_column!r} was not found."
        )

    timestamp = _quote_identifier(policy.timestamp_column)
    source = f"read_parquet({_quote_literal(parquet_path)})"
    count, null_count, distinct_count, minimum, maximum = connection.execute(
        f"""
        SELECT
            count(*),
            count(*) FILTER (WHERE {timestamp} IS NULL),
            count(DISTINCT {timestamp}),
            min({timestamp}),
            max({timestamp})
        FROM {source}
        """
    ).fetchone()
    if count == 0:
        raise TargetMaterializationError("Input Parquet contains no rows.")
    if null_count:
        raise TargetMaterializationError("Timestamp column contains null values.")
    if distinct_count != count:
        raise TargetMaterializationError("Timestamp column contains duplicate values.")

    expected_start = parse_timestamp(specification["dataset"]["start"], "dataset.start")
    expected_end = parse_timestamp(specification["dataset"]["end"], "dataset.end")
    if minimum != expected_start or maximum != expected_end:
        raise TargetMaterializationError(
            "Input timestamp coverage does not match the governed specification."
        )

    backwards = connection.execute(
        f"""
        SELECT count(*)
        FROM (
            SELECT
                ts,
                lag(ts) OVER (ORDER BY source_row_number) AS previous_ts
            FROM (
                SELECT
                    {timestamp} AS ts,
                    row_number() OVER () AS source_row_number
                FROM {source}
            )
        )
        WHERE previous_ts IS NOT NULL AND ts < previous_ts
        """
    ).fetchone()[0]
    if backwards:
        raise TargetMaterializationError("Input timestamps are not ordered.")

    return {
        "row_count": int(count),
        "timestamp_start": minimum.strftime(ISO_FORMAT),
        "timestamp_end": maximum.strftime(ISO_FORMAT),
        "parquet_sha256": actual_checksum,
    }


def _partition_case(specification: dict[str, Any], timestamp_expression: str) -> str:
    clauses: list[str] = []
    for name in ("train", "validation", "test"):
        interval = specification["evaluation"]["partitions"][name]
        clauses.append(
            "WHEN "
            f"{timestamp_expression} BETWEEN TIMESTAMP {_quote_literal(interval['start'])} "
            f"AND TIMESTAMP {_quote_literal(interval['end'])} THEN {_quote_literal(name)}"
        )
    return "CASE " + " ".join(clauses) + " ELSE NULL END"


def _event_case(
    intervals: list[Interval], timestamp_expression: str, result: str
) -> str:
    clauses = []
    for event in intervals:
        start = _quote_literal(event.start.strftime(ISO_FORMAT))
        end = _quote_literal(event.end.strftime(ISO_FORMAT))
        clauses.append(
            "WHEN "
            f"{timestamp_expression} BETWEEN TIMESTAMP {start} "
            f"AND TIMESTAMP {end} "
            f"THEN {_quote_literal(event.name if result == 'name' else result)}"
        )
    return "CASE " + " ".join(clauses) + " ELSE NULL END"


def _pre_event_case(
    intervals: list[Interval], timestamp_expression: str, hours: float
) -> str:
    clauses = []
    for event in intervals:
        start = event.start.strftime(ISO_FORMAT)
        clauses.append(
            "WHEN "
            f"{timestamp_expression} >= TIMESTAMP {_quote_literal(start)} - "
            f"INTERVAL {_quote_literal(f'{hours} hours')} "
            f"AND {timestamp_expression} < TIMESTAMP {_quote_literal(start)} "
            f"THEN {_quote_literal(event.name)}"
        )
    return "CASE " + " ".join(clauses) + " ELSE NULL END"


def _warning_case(
    intervals: list[Interval], timestamp_expression: str, warning_hours: float,
    exclusion_hours: float,
) -> str:
    clauses = []
    for event in intervals:
        start = event.start.strftime(ISO_FORMAT)
        clauses.append(
            "WHEN "
            f"{timestamp_expression} >= TIMESTAMP {_quote_literal(start)} - "
            f"INTERVAL {_quote_literal(f'{warning_hours} hours')} "
            f"AND {timestamp_expression} < TIMESTAMP {_quote_literal(start)} - "
            f"INTERVAL {_quote_literal(f'{exclusion_hours} hours')} "
            f"THEN {_quote_literal(event.name)}"
        )
    return "CASE " + " ".join(clauses) + " ELSE NULL END"


def _create_materialized_view(
    connection: duckdb.DuckDBPyConnection,
    parquet_path: Path,
    specification: dict[str, Any],
    policy: MaterializationPolicy,
) -> None:
    timestamp = _quote_identifier(policy.timestamp_column)
    source = f"read_parquet({_quote_literal(parquet_path)})"
    events = _event_intervals(specification)
    partition_case = _partition_case(specification, "timestamp")
    failure_case = _event_case(events, "timestamp", "name")
    exclusion_case = _pre_event_case(
        events, "timestamp", policy.pre_event_exclusion_hours
    )
    warning_case = (
        _warning_case(
            events,
            "timestamp",
            policy.warning_horizon_hours,
            policy.pre_event_exclusion_hours,
        )
        if policy.warning_horizon_hours is not None
        else "CAST(NULL AS VARCHAR)"
    )

    states = policy.states
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW governed_target_states AS
        WITH ordered AS (
            SELECT
                {timestamp} AS timestamp,
                lag({timestamp}) OVER (ORDER BY {timestamp}) AS previous_timestamp
            FROM {source}
        ),
        segmented AS (
            SELECT
                timestamp,
                sum(
                    CASE
                        WHEN previous_timestamp IS NULL
                          OR date_diff('second', previous_timestamp, timestamp)
                             > {policy.gap_threshold_seconds}
                        THEN 1 ELSE 0
                    END
                ) OVER (ORDER BY timestamp ROWS UNBOUNDED PRECEDING) AS segment_id
            FROM ordered
        ),
        classified AS (
            SELECT
                timestamp,
                segment_id,
                {partition_case} AS partition,
                {failure_case} AS failure_event,
                {exclusion_case} AS exclusion_event,
                {warning_case} AS warning_event
            FROM segmented
        ),
        anchored AS (
            SELECT
                *,
                min(segment_id) FILTER (WHERE failure_event IS NOT NULL)
                    OVER (PARTITION BY coalesce(failure_event, exclusion_event, warning_event))
                    AS event_segment_id
            FROM classified
        )
        SELECT
            timestamp,
            segment_id,
            partition,
            CASE
                WHEN partition IS NULL THEN {_quote_literal(states['partition_buffer_exclusion'])}
                WHEN failure_event IS NOT NULL THEN {_quote_literal(states['documented_failure'])}
                WHEN exclusion_event IS NOT NULL AND segment_id = event_segment_id
                    THEN {_quote_literal(states['pre_event_exclusion'])}
                WHEN warning_event IS NOT NULL AND segment_id = event_segment_id
                    THEN {_quote_literal(states['warning'])}
                ELSE {_quote_literal(states['unverified'])}
            END AS target_state,
            CASE
                WHEN partition IS NOT NULL AND failure_event IS NOT NULL THEN 1
                ELSE NULL
            END AS binary_target,
            CASE
                WHEN failure_event IS NOT NULL THEN failure_event
                WHEN exclusion_event IS NOT NULL AND segment_id = event_segment_id
                    THEN exclusion_event
                WHEN warning_event IS NOT NULL AND segment_id = event_segment_id
                    THEN warning_event
                ELSE NULL
            END AS source_event,
            CASE
                WHEN partition IS NULL THEN 'chronological_partition_buffer'
                WHEN exclusion_event IS NOT NULL AND segment_id = event_segment_id
                    THEN 'pre_event_exclusion_buffer'
                ELSE NULL
            END AS exclusion_reason
        FROM anchored
        ORDER BY timestamp
        """
    )


def _write_parquet_atomic(
    connection: duckdb.DuckDBPyConnection, output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.part")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        connection.execute(
            f"COPY governed_target_states TO {_quote_literal(temporary_path)} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def _build_report(
    connection: duckdb.DuckDBPyConnection,
    specification: dict[str, Any],
    policy: MaterializationPolicy,
    input_evidence: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    state_rows = connection.execute(
        """
        SELECT target_state, count(*) AS row_count
        FROM governed_target_states
        GROUP BY target_state
        ORDER BY target_state
        """
    ).fetchall()
    partition_rows = connection.execute(
        """
        SELECT coalesce(partition, 'excluded'), target_state, count(*)
        FROM governed_target_states
        GROUP BY partition, target_state
        ORDER BY coalesce(partition, 'excluded'), target_state
        """
    ).fetchall()
    segment_count = connection.execute(
        "SELECT count(DISTINCT segment_id) FROM governed_target_states"
    ).fetchone()[0]
    conflict_count = sum(
        len(event["provenance"]["source_conflicts"])
        for event in specification["events"]
    )
    assigned_cross_segment = connection.execute(
        """
        SELECT count(*)
        FROM governed_target_states
        WHERE target_state IN (?, ?)
          AND source_event IS NULL
        """,
        [policy.states["warning"], policy.states["pre_event_exclusion"]],
    ).fetchone()[0]

    return {
        "status": "valid",
        "schema_version": specification["schema_version"],
        "input": input_evidence,
        "output": {
            "path": output_path.as_posix(),
            "row_count": input_evidence["row_count"],
            "parquet_sha256": _sha256(output_path),
            "columns": [
                "timestamp",
                "segment_id",
                "partition",
                "target_state",
                "binary_target",
                "source_event",
                "exclusion_reason",
            ],
        },
        "policy": {
            "warning_horizon_hours": policy.warning_horizon_hours,
            "pre_event_exclusion_hours": policy.pre_event_exclusion_hours,
            "unverified_rows_are_negative": False,
            "source_conflicts_create_labels": False,
            "cross_segment_assignment_allowed": False,
        },
        "evidence": {
            "segment_count": int(segment_count),
            "state_counts": {name: int(count) for name, count in state_rows},
            "partition_state_counts": [
                {"partition": partition, "target_state": state, "row_count": int(count)}
                for partition, state, count in partition_rows
            ],
            "documented_event_count": len(specification["events"]),
            "preserved_provenance_conflict_count": conflict_count,
            "cross_segment_assignment_count": int(assigned_cross_segment),
        },
        "scope": {
            "row_level_target_states_created": True,
            "verified_negative_class_created": False,
            "features_engineered": False,
            "models_trained": False,
            "performance_reported": False,
        },
    }


def write_json_atomic(payload: dict[str, Any], output_path: Path) -> Path:
    """Write JSON through a temporary file and atomic replace."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.part")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise
    return output_path


def materialize_targets(
    specification_path: Path,
    parquet_path: Path,
    output_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Validate inputs, create the row-state Parquet, and write audit evidence."""
    specification = load_specification(specification_path)
    validate_specification(specification)
    policy = validate_materialization_policy(specification)
    connection = duckdb.connect(database=":memory:")
    output_created = False
    try:
        input_evidence = _validate_input(
            connection, parquet_path, specification, policy
        )
        _create_materialized_view(
            connection, parquet_path, specification, policy
        )
        _write_parquet_atomic(connection, output_path)
        output_created = True
        report = _build_report(
            connection, specification, policy, input_evidence, output_path
        )
        write_json_atomic(report, report_path)
        return report
    except duckdb.Error as exc:
        for path in (output_path, report_path):
            temporary = path.with_name(f"{path.name}.part")
            if temporary.exists():
                temporary.unlink()
        if output_created and output_path.exists():
            output_path.unlink()
        raise TargetMaterializationError(f"DuckDB materialization failed: {exc}") from exc
    except Exception:
        for path in (output_path, report_path):
            temporary = path.with_name(f"{path.name}.part")
            if temporary.exists():
                temporary.unlink()
        if output_created and output_path.exists():
            output_path.unlink()
        raise
    finally:
        connection.close()


def main() -> int:
    """Run governed row-level target-state materialization."""
    parser = argparse.ArgumentParser(
        description="Materialize governed MetroPT-3 row-level target states."
    )
    parser.add_argument("specification", type=Path)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = materialize_targets(
            args.specification, args.parquet, args.output, args.report
        )
    except (TargetDefinitionError, TargetMaterializationError) as exc:
        parser.exit(1, f"Target materialization failed: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

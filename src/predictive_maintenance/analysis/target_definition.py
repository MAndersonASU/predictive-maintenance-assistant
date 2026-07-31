"""Validate source-traceable target definitions and temporal evaluation boundaries.

This module validates a governed JSON specification for documented failure
intervals, optional prediction windows, provenance conflicts, and chronological
evaluation partitions. It intentionally does not create row-level labels,
engineer features, train models, or publish performance metrics.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"
ALLOWED_CONFIDENCE = {"documented", "derived", "ambiguous"}
ALLOWED_DATASET_MATCH = {"exact", "related", "unknown"}


class TargetDefinitionError(ValueError):
    """Raised when a target-definition specification is invalid."""


@dataclass(frozen=True, order=True)
class Interval:
    """One inclusive timestamp interval."""

    start: datetime
    end: datetime
    name: str

    def overlaps(self, other: "Interval") -> bool:
        """Return whether two inclusive intervals overlap."""
        return self.start <= other.end and other.start <= self.end


def parse_timestamp(value: Any, field_name: str) -> datetime:
    """Parse a second-resolution ISO-8601 timestamp."""
    if not isinstance(value, str):
        raise TargetDefinitionError(f"{field_name} must be a string.")
    try:
        return datetime.strptime(value, ISO_FORMAT)
    except ValueError as exc:
        raise TargetDefinitionError(
            f"{field_name} must use YYYY-MM-DDTHH:MM:SS: {value!r}"
        ) from exc


def parse_date(value: Any, field_name: str) -> date:
    """Parse an ISO calendar date."""
    if not isinstance(value, str):
        raise TargetDefinitionError(f"{field_name} must be a string.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise TargetDefinitionError(
            f"{field_name} must use YYYY-MM-DD: {value!r}"
        ) from exc


def require_nonempty_string(payload: dict[str, Any], key: str, prefix: str) -> str:
    """Read one required, non-empty string field."""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TargetDefinitionError(f"{prefix}.{key} must be a non-empty string.")
    return value.strip()


def parse_interval(payload: dict[str, Any], prefix: str) -> Interval:
    """Create and validate one interval from a JSON object."""
    name = require_nonempty_string(payload, "name", prefix)
    start = parse_timestamp(payload.get("start"), f"{prefix}.start")
    end = parse_timestamp(payload.get("end"), f"{prefix}.end")
    if end < start:
        raise TargetDefinitionError(f"{prefix} ends before it starts.")
    return Interval(start=start, end=end, name=name)


def validate_source_conflicts(provenance: dict[str, Any], prefix: str) -> int:
    """Validate explicitly recorded source conflicts and return their count."""
    conflicts = provenance.get("source_conflicts")
    if not isinstance(conflicts, list):
        raise TargetDefinitionError(f"{prefix}.source_conflicts must be a list.")
    for index, conflict in enumerate(conflicts):
        if not isinstance(conflict, str) or not conflict.strip():
            raise TargetDefinitionError(
                f"{prefix}.source_conflicts[{index}] must be a non-empty string."
            )
    return len(conflicts)


def validate_provenance(event: dict[str, Any], prefix: str) -> tuple[str, int]:
    """Require exact source identity, traceability, and conflict preservation."""
    provenance = event.get("provenance")
    if not isinstance(provenance, dict):
        raise TargetDefinitionError(f"{prefix}.provenance must be an object.")

    for key in (
        "source_title",
        "source_type",
        "source_identifier",
        "source_locator",
        "interpretation",
    ):
        require_nonempty_string(provenance, key, f"{prefix}.provenance")

    parse_date(provenance.get("accessed_on"), f"{prefix}.provenance.accessed_on")

    confidence = provenance.get("confidence")
    if confidence not in ALLOWED_CONFIDENCE:
        raise TargetDefinitionError(
            f"{prefix}.provenance.confidence must be documented, derived, or ambiguous."
        )

    dataset_match = provenance.get("dataset_match")
    if dataset_match not in ALLOWED_DATASET_MATCH:
        raise TargetDefinitionError(
            f"{prefix}.provenance.dataset_match must be exact, related, or unknown."
        )
    if confidence == "documented" and dataset_match != "exact":
        raise TargetDefinitionError(
            f"{prefix} cannot be documented unless provenance.dataset_match is exact."
        )

    conflict_count = validate_source_conflicts(
        provenance, f"{prefix}.provenance"
    )
    return confidence, conflict_count


def validate_prediction_window(
    event: dict[str, Any],
    event_interval: Interval,
    minimum_warning_hours: float,
    prefix: str,
) -> Interval | None:
    """Validate an optional prediction window that precedes an observed event."""
    payload = event.get("prediction_window")
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise TargetDefinitionError(
            f"{prefix}.prediction_window must be an object or null."
        )

    window = parse_interval(payload, f"{prefix}.prediction_window")
    if window.end >= event_interval.start:
        raise TargetDefinitionError(
            f"{prefix}.prediction_window must end before the observed event starts."
        )

    available_warning = event_interval.start - window.end
    required_warning = timedelta(hours=minimum_warning_hours)
    if available_warning < required_warning:
        hours = available_warning.total_seconds() / 3600
        raise TargetDefinitionError(
            f"{prefix}.prediction_window provides only {hours:.3f} hours of warning; "
            f"{minimum_warning_hours:.3f} hours are required."
        )
    return window


def assert_no_overlaps(intervals: Iterable[Interval], label: str) -> None:
    """Reject adjacent sorted intervals that overlap."""
    ordered = sorted(intervals)
    for left, right in zip(ordered, ordered[1:]):
        if left.overlaps(right):
            raise TargetDefinitionError(
                f"{label} intervals overlap: {left.name!r} and {right.name!r}."
            )


def validate_partitions(
    partitions: dict[str, Any],
    dataset_start: datetime,
    dataset_end: datetime,
    buffer_hours: float,
) -> dict[str, Interval]:
    """Validate chronological train, validation, and test boundaries."""
    parsed: dict[str, Interval] = {}
    for name in ("train", "validation", "test"):
        payload = partitions.get(name)
        if not isinstance(payload, dict):
            raise TargetDefinitionError(
                f"evaluation.partitions.{name} must be an object."
            )
        normalized = dict(payload)
        normalized["name"] = name
        parsed[name] = parse_interval(normalized, f"evaluation.partitions.{name}")

    if parsed["train"].start < dataset_start or parsed["test"].end > dataset_end:
        raise TargetDefinitionError("Evaluation partitions exceed dataset coverage.")

    if not (
        parsed["train"].end < parsed["validation"].start
        and parsed["validation"].end < parsed["test"].start
    ):
        raise TargetDefinitionError(
            "Partitions must be strictly chronological and non-overlapping."
        )

    minimum_buffer = timedelta(hours=buffer_hours)
    train_gap = parsed["validation"].start - parsed["train"].end
    validation_gap = parsed["test"].start - parsed["validation"].end
    if train_gap < minimum_buffer or validation_gap < minimum_buffer:
        raise TargetDefinitionError(
            f"Each partition boundary must retain at least {buffer_hours:.3f} hours."
        )

    return parsed


def validate_specification(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a complete governed target-definition specification."""
    if payload.get("schema_version") != 2:
        raise TargetDefinitionError("schema_version must equal 2.")

    dataset = payload.get("dataset")
    if not isinstance(dataset, dict):
        raise TargetDefinitionError("dataset must be an object.")
    require_nonempty_string(dataset, "name", "dataset")
    require_nonempty_string(dataset, "source_identifier", "dataset")
    checksum = require_nonempty_string(dataset, "parquet_sha256", "dataset")
    if len(checksum) != 64 or any(
        char not in "0123456789abcdef" for char in checksum.lower()
    ):
        raise TargetDefinitionError(
            "dataset.parquet_sha256 must be a 64-character hexadecimal SHA-256 value."
        )

    dataset_start = parse_timestamp(dataset.get("start"), "dataset.start")
    dataset_end = parse_timestamp(dataset.get("end"), "dataset.end")
    if dataset_end < dataset_start:
        raise TargetDefinitionError("dataset.end precedes dataset.start.")

    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise TargetDefinitionError("policy must be an object.")

    minimum_warning_hours = policy.get("minimum_warning_hours")
    partition_buffer_hours = policy.get("partition_buffer_hours")
    if not isinstance(minimum_warning_hours, (int, float)) or minimum_warning_hours <= 0:
        raise TargetDefinitionError("policy.minimum_warning_hours must be positive.")
    if not isinstance(partition_buffer_hours, (int, float)) or partition_buffer_hours < 0:
        raise TargetDefinitionError("policy.partition_buffer_hours cannot be negative.")
    if policy.get("unlabeled_rows_are_assumed_normal") is not False:
        raise TargetDefinitionError(
            "policy.unlabeled_rows_are_assumed_normal must be false."
        )
    if policy.get("ambiguous_periods_are_excluded") is not True:
        raise TargetDefinitionError("policy.ambiguous_periods_are_excluded must be true.")

    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise TargetDefinitionError("events must be a non-empty list.")

    event_intervals: list[Interval] = []
    prediction_windows: list[Interval] = []
    event_names: set[str] = set()
    documented_event_count = 0
    derived_event_count = 0
    ambiguous_event_count = 0
    provenance_conflict_count = 0

    for index, event in enumerate(events):
        prefix = f"events[{index}]"
        if not isinstance(event, dict):
            raise TargetDefinitionError(f"{prefix} must be an object.")

        interval = parse_interval(event, prefix)
        if interval.name in event_names:
            raise TargetDefinitionError(f"Duplicate event name: {interval.name!r}.")
        event_names.add(interval.name)

        if interval.start < dataset_start or interval.end > dataset_end:
            raise TargetDefinitionError(f"{prefix} exceeds dataset coverage.")

        confidence, conflict_count = validate_provenance(event, prefix)
        documented_event_count += int(confidence == "documented")
        derived_event_count += int(confidence == "derived")
        ambiguous_event_count += int(confidence == "ambiguous")
        provenance_conflict_count += conflict_count

        prediction_window = validate_prediction_window(
            event,
            interval,
            float(minimum_warning_hours),
            prefix,
        )
        event_intervals.append(interval)
        if prediction_window is not None:
            prediction_windows.append(prediction_window)

    assert_no_overlaps(event_intervals, "Observed event")
    assert_no_overlaps(prediction_windows, "Prediction window")

    evaluation = payload.get("evaluation")
    if not isinstance(evaluation, dict):
        raise TargetDefinitionError("evaluation must be an object.")
    partitions = evaluation.get("partitions")
    if not isinstance(partitions, dict):
        raise TargetDefinitionError("evaluation.partitions must be an object.")

    parsed_partitions = validate_partitions(
        partitions,
        dataset_start,
        dataset_end,
        float(partition_buffer_hours),
    )

    controls = evaluation.get("leakage_controls")
    required_controls = (
        "chronological_only",
        "segment_bounded_windows",
        "training_only_fit",
        "event_isolation",
    )
    if not isinstance(controls, dict):
        raise TargetDefinitionError("evaluation.leakage_controls must be an object.")
    for control in required_controls:
        if controls.get(control) is not True:
            raise TargetDefinitionError(
                f"evaluation.leakage_controls.{control} must be true."
            )

    return {
        "status": "valid",
        "schema_version": 2,
        "event_count": len(event_intervals),
        "documented_event_count": documented_event_count,
        "derived_event_count": derived_event_count,
        "ambiguous_event_count": ambiguous_event_count,
        "provenance_conflict_count": provenance_conflict_count,
        "prediction_window_count": len(prediction_windows),
        "minimum_warning_hours": float(minimum_warning_hours),
        "partition_buffer_hours": float(partition_buffer_hours),
        "partitions": {
            name: {
                "start": interval.start.strftime(ISO_FORMAT),
                "end": interval.end.strftime(ISO_FORMAT),
            }
            for name, interval in parsed_partitions.items()
        },
        "scope": {
            "row_level_labels_created": False,
            "features_engineered": False,
            "models_trained": False,
            "performance_reported": False,
        },
    }


def load_and_validate(path: Path) -> dict[str, Any]:
    """Load and validate a JSON target-definition file."""
    if not path.exists():
        raise TargetDefinitionError(f"Specification does not exist: {path}")
    if not path.is_file():
        raise TargetDefinitionError(f"Specification path is not a file: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TargetDefinitionError(f"Invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise TargetDefinitionError("The top-level JSON value must be an object.")
    return validate_specification(payload)


def write_report_atomic(report: dict[str, Any], output_path: Path) -> Path:
    """Write a validation report through a temporary file and atomic replace."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.part")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        temporary_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise
    return output_path


def main() -> int:
    """Run command-line specification validation."""
    parser = argparse.ArgumentParser(
        description="Validate source-traceable target and temporal-evaluation design."
    )
    parser.add_argument("specification", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        report = load_and_validate(args.specification)
        if args.report:
            write_report_atomic(report, args.report)
    except TargetDefinitionError as exc:
        parser.exit(1, f"Target-definition validation failed: {exc}\n")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

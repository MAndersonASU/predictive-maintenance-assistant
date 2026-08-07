"""Train, validate, and freeze the governed MetroPT-3 Isolation Forest candidate.

The workflow evaluates exactly the eight candidates authorized by the frozen
advanced-model comparison contract. Every candidate is fitted on eligible
training-reference rows, receives a threshold from the 0.995 quantile of its
training scores, and is ranked with validation evidence only. Test rows are
never loaded or scored.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import platform
from pathlib import Path
from typing import Any, Iterable

import duckdb
import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import sklearn
from sklearn.ensemble import IsolationForest

from predictive_maintenance.analysis.advanced_model_comparison import (
    AdvancedModelComparisonError,
    load_contract as load_comparison_contract,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "metropt3_isolation_forest_validation.json"
EXPECTED_EXECUTION_KEYS = {
    "fit_partition": "train",
    "selection_partition": "validation",
    "fit_eligibility_column": "eligible_for_reference_fit",
    "scoring_eligibility_column": "eligible_for_scoring",
    "known_event_eligibility_column": "eligible_for_known_event_evaluation",
    "alarm_burden_eligibility_column": "eligible_for_alarm_burden",
    "expected_retained_feature_count": 48,
    "expected_sampling_seconds": 10.0,
    "matrix_dtype": "float32",
    "threshold_comparison": "strictly_greater_than",
}
EXPECTED_TRUE_GOVERNANCE = (
    "model_fitting_enabled",
    "candidate_scoring_enabled",
    "candidate_selection_enabled",
)
EXPECTED_FALSE_GOVERNANCE = (
    "validation_threshold_tuning_enabled",
    "test_partition_access_enabled",
    "test_scoring_enabled",
    "baseline_revision_enabled",
    "unsupported_classification_metrics_enabled",
    "unverified_rows_are_verified_healthy",
    "alarm_burden_is_false_positive_rate",
)


class IsolationForestValidationError(ValueError):
    """Raised when the governed training-and-validation workflow is unsafe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise IsolationForestValidationError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise IsolationForestValidationError(f"Invalid {label} JSON: {error}") from error
    if not isinstance(payload, dict):
        raise IsolationForestValidationError(f"{label} must contain a JSON object.")
    return payload


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _resolve_project_path(relative_path: str, label: str) -> Path:
    root = PROJECT_ROOT.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise IsolationForestValidationError(f"{label} escapes the project root: {relative_path}")
    return candidate


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def validate_execution_contract(contract: dict[str, Any]) -> None:
    """Validate the Day 16 execution authorization without changing Day 15."""
    if contract.get("schema_version") != 1:
        raise IsolationForestValidationError("schema_version must be 1.")
    for section in ("comparison_contract", "dataset", "execution", "governance", "outputs"):
        if not isinstance(contract.get(section), dict):
            raise IsolationForestValidationError(f"Execution-contract section must be an object: {section}")

    comparison = contract["comparison_contract"]
    if comparison != {
        "path": "config/metropt3_advanced_model_comparison.json",
        "validation_report_path": "outputs/metropt3_advanced_model_comparison_contract_report.json",
        "required_status": "valid",
    }:
        raise IsolationForestValidationError("The frozen comparison-contract evidence paths were changed.")

    dataset = contract["dataset"]
    expected_dataset = {
        "feature_parquet_path": "data/processed/metropt3_features.parquet",
        "feature_evidence_path": "outputs/metropt3_feature_engineering_report.json",
        "eligibility_parquet_path": "data/processed/metropt3_baseline_eligibility.parquet",
        "eligibility_evidence_path": "outputs/metropt3_baseline_evaluation_contract_report.json",
        "frozen_feature_parameters_path": "outputs/metropt3_robust_distance_parameters.json",
    }
    if dataset != expected_dataset:
        raise IsolationForestValidationError("The governed feature, eligibility, or frozen-feature inputs were changed.")

    execution = contract["execution"]
    if execution != EXPECTED_EXECUTION_KEYS:
        raise IsolationForestValidationError("The governed fit, validation, feature-count, or threshold controls were changed.")

    governance = contract["governance"]
    for key in EXPECTED_TRUE_GOVERNANCE:
        if governance.get(key) is not True:
            raise IsolationForestValidationError(f"governance.{key} must be true.")
    for key in EXPECTED_FALSE_GOVERNANCE:
        if governance.get(key) is not False:
            raise IsolationForestValidationError(f"governance.{key} must be false.")

    outputs = contract["outputs"]
    if outputs.get("selected_model") != "outputs/metropt3_selected_isolation_forest.joblib":
        raise IsolationForestValidationError("The selected-model output path is incorrect.")
    if outputs.get("selected_validation_scores") != "data/processed/metropt3_validation_isolation_forest.parquet":
        raise IsolationForestValidationError("The selected validation-score output path is incorrect.")
    if outputs.get("validation_decision_report") != "outputs/metropt3_isolation_forest_validation_report.json":
        raise IsolationForestValidationError("The validation-decision report path is incorrect.")
    if outputs.get("parquet_compression") != "zstd" or outputs.get("joblib_compression") != 3:
        raise IsolationForestValidationError("The governed output-compression settings were changed.")


def load_execution_contract(path: Path) -> dict[str, Any]:
    contract = _read_json(path, "Isolation Forest validation execution contract")
    validate_execution_contract(contract)
    return contract


def build_candidate_grid(comparison_contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the exact bounded grid with deterministic complexity ranks."""
    candidate = comparison_contract["candidate_model"]
    fixed = candidate["fixed_parameters"]
    grid = candidate["bounded_grid"]
    combinations = list(
        itertools.product(
            sorted(grid["n_estimators"]),
            sorted(grid["max_samples"]),
            sorted(grid["max_features"]),
        )
    )
    if len(combinations) != candidate["candidate_count"] or len(combinations) != 8:
        raise IsolationForestValidationError("The frozen comparison contract must produce exactly eight candidates.")
    candidates: list[dict[str, Any]] = []
    for rank, (n_estimators, max_samples, max_features) in enumerate(combinations, start=1):
        candidates.append(
            {
                "candidate_id": candidate_id(n_estimators, max_samples, max_features),
                "complexity_rank": rank,
                "n_estimators": int(n_estimators),
                "max_samples": int(max_samples),
                "max_features": float(max_features),
                "contamination": fixed["contamination"],
                "bootstrap": fixed["bootstrap"],
                "random_state": fixed["random_state"],
                "n_jobs": fixed["n_jobs"],
            }
        )
    return candidates


def candidate_id(n_estimators: int, max_samples: int, max_features: float) -> str:
    feature_token = str(max_features).replace(".", "p")
    return f"iforest_ne{n_estimators}_ms{max_samples}_mf{feature_token}"


def build_model(candidate: dict[str, Any]) -> IsolationForest:
    return IsolationForest(
        n_estimators=candidate["n_estimators"],
        max_samples=candidate["max_samples"],
        max_features=candidate["max_features"],
        contamination=candidate["contamination"],
        bootstrap=candidate["bootstrap"],
        random_state=candidate["random_state"],
        n_jobs=candidate["n_jobs"],
    )


def _score_summary(values: np.ndarray) -> dict[str, float | int]:
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise IsolationForestValidationError("Score summaries require a non-empty finite one-dimensional array.")
    return {
        "row_count": int(values.size),
        "minimum": float(np.min(values)),
        "median": float(np.quantile(values, 0.5)),
        "p95": float(np.quantile(values, 0.95)),
        "p995": float(np.quantile(values, 0.995)),
        "maximum": float(np.max(values)),
    }


def _longest_contiguous_alarm_run(
    timestamps: np.ndarray,
    alarms: np.ndarray,
    expected_sampling_seconds: float,
) -> int:
    longest = 0
    current = 0
    previous: np.datetime64 | None = None
    maximum_gap = np.timedelta64(int(round(expected_sampling_seconds * 1_500_000)), "us")
    for timestamp, alarm in zip(timestamps, alarms, strict=True):
        if not bool(alarm):
            current = 0
            previous = timestamp
            continue
        if previous is None or timestamp - previous <= maximum_gap:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        previous = timestamp
    return longest


def event_evidence(
    timestamps: np.ndarray,
    source_events: np.ndarray,
    eligible: np.ndarray,
    alarms: np.ndarray,
    expected_sampling_seconds: float,
) -> list[dict[str, Any]]:
    """Calculate documented-event coverage, latency, and alarm contiguity."""
    if not (len(timestamps) == len(source_events) == len(eligible) == len(alarms)):
        raise IsolationForestValidationError("Event-evidence arrays must have equal lengths.")
    ordered_events: list[str] = []
    seen: set[str] = set()
    for raw_event, is_eligible in zip(source_events, eligible, strict=True):
        if not bool(is_eligible):
            continue
        event = str(raw_event)
        if event not in seen:
            seen.add(event)
            ordered_events.append(event)

    evidence: list[dict[str, Any]] = []
    for event in ordered_events:
        mask = np.asarray([bool(flag) and str(value) == event for value, flag in zip(source_events, eligible, strict=True)])
        event_times = timestamps[mask]
        event_alarms = alarms[mask]
        if event_times.size == 0:
            continue
        first_alarm_index = np.flatnonzero(event_alarms)
        first_alarm = None if first_alarm_index.size == 0 else event_times[int(first_alarm_index[0])]
        latency = None
        if first_alarm is not None:
            latency = float((first_alarm - event_times[0]) / np.timedelta64(1, "s"))
        longest_run = _longest_contiguous_alarm_run(event_times, event_alarms, expected_sampling_seconds)
        alarm_rows = int(np.count_nonzero(event_alarms))
        evidence.append(
            {
                "source_event": event,
                "event_start": np.datetime_as_string(event_times[0], unit="s"),
                "event_rows": int(event_times.size),
                "covered": first_alarm is not None,
                "first_alarm_latency_seconds": latency,
                "alarm_rows_within_documented_event": alarm_rows,
                "longest_contiguous_alarm_run_rows": longest_run,
                "longest_contiguous_alarm_run_seconds": float(longest_run * expected_sampling_seconds),
                "alarm_contiguity_fraction": longest_run / int(event_times.size),
            }
        )
    return evidence


def candidate_metrics(
    train_scores: np.ndarray,
    validation_scores: np.ndarray,
    validation_timestamps: np.ndarray,
    source_events: np.ndarray,
    known_event_eligible: np.ndarray,
    alarm_burden_eligible: np.ndarray,
    threshold: float,
    expected_sampling_seconds: float,
) -> tuple[dict[str, Any], np.ndarray]:
    alarms = validation_scores > threshold
    events = event_evidence(
        validation_timestamps,
        source_events,
        known_event_eligible,
        alarms,
        expected_sampling_seconds,
    )
    covered_latencies = [item["first_alarm_latency_seconds"] for item in events if item["covered"]]
    burden_rows = int(np.count_nonzero(alarm_burden_eligible))
    burden_alarms = int(np.count_nonzero(alarms & alarm_burden_eligible.astype(bool)))
    observed_hours = burden_rows * expected_sampling_seconds / 3600.0
    train_summary = _score_summary(train_scores)
    validation_summary = _score_summary(validation_scores)
    p95_ratio = None
    if train_summary["p95"] != 0:
        p95_ratio = validation_summary["p95"] / train_summary["p95"]
    metrics = {
        "threshold": float(threshold),
        "training_score_summary": train_summary,
        "validation_score_summary": validation_summary,
        "documented_event_count": len(events),
        "documented_events_covered": len(covered_latencies),
        "documented_event_coverage": None if not events else len(covered_latencies) / len(events),
        "mean_first_alarm_latency_seconds_for_covered_events": (
            None if not covered_latencies else float(np.mean(covered_latencies))
        ),
        "documented_event_evidence": events,
        "alarm_burden_rows": burden_rows,
        "alarm_count_on_burden_population": burden_alarms,
        "alarm_burden_fraction": None if burden_rows == 0 else burden_alarms / burden_rows,
        "alarms_per_24_observed_hours": (
            None if observed_hours == 0 else burden_alarms * 24.0 / observed_hours
        ),
        "score_distribution_drift": {
            "validation_minus_training_median": validation_summary["median"] - train_summary["median"],
            "validation_to_training_p95_ratio": p95_ratio,
        },
    }
    return metrics, alarms


def selection_key(candidate_result: dict[str, Any]) -> tuple[float, float, float, int]:
    """Map the frozen lexicographic rule to an ascending Python tuple."""
    coverage = candidate_result["metrics"]["documented_event_coverage"]
    latency = candidate_result["metrics"]["mean_first_alarm_latency_seconds_for_covered_events"]
    burden = candidate_result["metrics"]["alarms_per_24_observed_hours"]
    return (
        -float(coverage if coverage is not None else -1.0),
        float(latency if latency is not None else math.inf),
        float(burden if burden is not None else math.inf),
        int(candidate_result["complexity_rank"]),
    )


def _validate_comparison_evidence(
    comparison_contract_path: Path,
    comparison_report_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        comparison_contract = load_comparison_contract(comparison_contract_path)
    except AdvancedModelComparisonError as error:
        raise IsolationForestValidationError(str(error)) from error
    comparison_report = _read_json(comparison_report_path, "Advanced-model comparison validation report")
    if comparison_report.get("status") != "valid":
        raise IsolationForestValidationError("The advanced-model comparison validation report must be valid.")
    if comparison_report.get("contract", {}).get("sha256") != _sha256(comparison_contract_path):
        raise IsolationForestValidationError("The comparison validation report does not match the current contract.")
    scope = comparison_report.get("scope", {})
    if scope.get("advanced_model_fitted") is not False or scope.get("advanced_test_partition_accessed") is not False:
        raise IsolationForestValidationError("Day 15 evidence must show no model fitting and no test access.")
    if comparison_report.get("candidate_boundary", {}).get("candidate_count") != 8:
        raise IsolationForestValidationError("Day 15 evidence must authorize exactly eight candidates.")
    return comparison_contract, comparison_report


def _validate_upstream_inputs(
    connection: duckdb.DuckDBPyConnection,
    feature_path: Path,
    feature_report_path: Path,
    eligibility_path: Path,
    eligibility_report_path: Path,
    parameters_path: Path,
    expected_feature_count: int,
) -> tuple[list[str], dict[str, Any]]:
    for path, label in (
        (feature_path, "Feature Parquet"),
        (eligibility_path, "Eligibility Parquet"),
        (parameters_path, "Frozen robust-distance parameters"),
    ):
        if not path.is_file():
            raise IsolationForestValidationError(f"{label} does not exist: {path}")

    feature_report = _read_json(feature_report_path, "Feature evidence")
    eligibility_report = _read_json(eligibility_report_path, "Eligibility evidence")
    parameters = _read_json(parameters_path, "Frozen robust-distance parameters")
    if feature_report.get("status") != "valid" or eligibility_report.get("status") != "valid":
        raise IsolationForestValidationError("Upstream feature and eligibility evidence must both be valid.")
    feature_sha = _sha256(feature_path)
    eligibility_sha = _sha256(eligibility_path)
    if feature_report.get("output", {}).get("parquet_sha256") != feature_sha:
        raise IsolationForestValidationError("Feature Parquet SHA-256 does not match its evidence report.")
    if eligibility_report.get("output", {}).get("parquet_sha256") != eligibility_sha:
        raise IsolationForestValidationError("Eligibility Parquet SHA-256 does not match its evidence report.")
    if parameters.get("status") != "frozen_before_validation" or parameters.get("test_partition_used") is not False:
        raise IsolationForestValidationError("The retained feature set must be frozen before validation without test use.")
    retained = parameters.get("retained_features")
    if not isinstance(retained, list):
        raise IsolationForestValidationError("Frozen robust-distance parameters must list retained features.")
    feature_names = [item.get("feature") for item in retained if isinstance(item, dict)]
    if len(feature_names) != expected_feature_count or len(set(feature_names)) != expected_feature_count:
        raise IsolationForestValidationError(f"The frozen retained feature set must contain {expected_feature_count} unique features.")
    if parameters.get("eligible_reference_rows") in (None, 0):
        raise IsolationForestValidationError("Frozen robust-distance parameters must record a non-empty reference population.")

    described = connection.execute(
        f"DESCRIBE SELECT * FROM read_parquet({_quote_literal(feature_path)})"
    ).fetchall()
    available = {str(row[0]): str(row[1]).upper() for row in described}
    numeric_prefixes = (
        "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "FLOAT", "DOUBLE", "DECIMAL",
        "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
    )
    for feature in feature_names:
        if feature not in available:
            raise IsolationForestValidationError(f"Frozen feature is missing from the feature Parquet: {feature}")
        if not available[feature].startswith(numeric_prefixes):
            raise IsolationForestValidationError(f"Frozen feature is not numeric: {feature}")

    development_rows = int(
        connection.execute(
            f"SELECT count(*) FROM read_parquet({_quote_literal(feature_path)}) "
            "WHERE partition IN ('train', 'validation')"
        ).fetchone()[0]
    )
    joined_rows = int(
        connection.execute(
            f"SELECT count(*) FROM read_parquet({_quote_literal(feature_path)}) f "
            f"INNER JOIN read_parquet({_quote_literal(eligibility_path)}) e USING (timestamp) "
            "WHERE f.partition IN ('train', 'validation')"
        ).fetchone()[0]
    )
    if development_rows == 0 or joined_rows != development_rows:
        raise IsolationForestValidationError("Train/validation feature and eligibility timestamps must match one-to-one.")

    evidence = {
        "feature_parquet_sha256": feature_sha,
        "eligibility_parquet_sha256": eligibility_sha,
        "frozen_feature_parameters_sha256": _sha256(parameters_path),
        "development_rows": development_rows,
        "frozen_reference_rows": int(parameters["eligible_reference_rows"]),
        "retained_feature_count": len(feature_names),
        "retained_feature_names_sha256": hashlib.sha256(
            ("\n".join(feature_names) + "\n").encode("utf-8")
        ).hexdigest(),
    }
    return feature_names, evidence


def _matrix_from_columns(columns: dict[str, np.ndarray], feature_names: Iterable[str]) -> np.ndarray:
    matrix = np.column_stack([np.asarray(columns[name], dtype=np.float32) for name in feature_names])
    if matrix.ndim != 2 or matrix.shape[0] == 0 or not np.isfinite(matrix).all():
        raise IsolationForestValidationError("Model matrices must be non-empty, two-dimensional, and finite.")
    return matrix


def _load_development_populations(
    connection: duckdb.DuckDBPyConnection,
    feature_path: Path,
    eligibility_path: Path,
    feature_names: list[str],
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    feature_sql = ", ".join(f"CAST(f.{_quote_identifier(name)} AS FLOAT) AS {_quote_identifier(name)}" for name in feature_names)
    train_columns = connection.execute(
        f"SELECT {feature_sql} "
        f"FROM read_parquet({_quote_literal(feature_path)}) f "
        f"INNER JOIN read_parquet({_quote_literal(eligibility_path)}) e USING (timestamp) "
        "WHERE f.partition = 'train' AND e.eligible_for_reference_fit "
        "ORDER BY f.timestamp"
    ).fetchnumpy()
    validation_columns = connection.execute(
        f"SELECT f.timestamp, f.segment_id, f.partition, f.target_state, f.source_event, "
        "e.eligible_for_known_event_evaluation, e.eligible_for_alarm_burden, "
        f"{feature_sql} "
        f"FROM read_parquet({_quote_literal(feature_path)}) f "
        f"INNER JOIN read_parquet({_quote_literal(eligibility_path)}) e USING (timestamp) "
        "WHERE f.partition = 'validation' AND e.eligible_for_scoring "
        "ORDER BY f.timestamp"
    ).fetchnumpy()
    train_matrix = _matrix_from_columns(train_columns, feature_names)
    validation_matrix = _matrix_from_columns(validation_columns, feature_names)
    if set(np.unique(validation_columns["partition"])) != {"validation"}:
        raise IsolationForestValidationError("Validation loading included a non-validation partition.")
    return train_matrix, validation_matrix, validation_columns


def _write_selected_scores(
    path: Path,
    metadata: dict[str, np.ndarray],
    candidate_identifier: str,
    scores: np.ndarray,
    alarms: np.ndarray,
    compression: str,
) -> None:
    table = pa.table(
        {
            "timestamp": pa.array(metadata["timestamp"]),
            "segment_id": pa.array(metadata["segment_id"]),
            "partition": pa.array(metadata["partition"]),
            "target_state": pa.array(metadata["target_state"]),
            "source_event": pa.array(metadata["source_event"]),
            "eligible_for_known_event_evaluation": pa.array(metadata["eligible_for_known_event_evaluation"]),
            "eligible_for_alarm_burden": pa.array(metadata["eligible_for_alarm_burden"]),
            "candidate_id": pa.array([candidate_identifier] * len(scores), type=pa.string()),
            "isolation_forest_score": pa.array(scores, type=pa.float64()),
            "alarm": pa.array(alarms, type=pa.bool_()),
        }
    )
    pq.write_table(table, path, compression=compression)


def run_isolation_forest_validation(
    config_path: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the frozen eight-candidate training-and-validation comparison."""
    execution_contract = load_execution_contract(config_path)
    comparison_section = execution_contract["comparison_contract"]
    comparison_contract_path = _resolve_project_path(comparison_section["path"], "comparison contract")
    comparison_report_path = _resolve_project_path(
        comparison_section["validation_report_path"], "comparison validation report"
    )
    comparison_contract, comparison_report = _validate_comparison_evidence(
        comparison_contract_path, comparison_report_path
    )
    candidates = build_candidate_grid(comparison_contract)

    dataset = execution_contract["dataset"]
    feature_path = _resolve_project_path(dataset["feature_parquet_path"], "feature Parquet")
    feature_report_path = _resolve_project_path(dataset["feature_evidence_path"], "feature evidence")
    eligibility_path = _resolve_project_path(dataset["eligibility_parquet_path"], "eligibility Parquet")
    eligibility_report_path = _resolve_project_path(dataset["eligibility_evidence_path"], "eligibility evidence")
    parameters_path = _resolve_project_path(dataset["frozen_feature_parameters_path"], "frozen features")

    outputs = execution_contract["outputs"]
    model_path = _resolve_project_path(outputs["selected_model"], "selected model")
    scores_path = _resolve_project_path(outputs["selected_validation_scores"], "selected validation scores")
    report_path = _resolve_project_path(outputs["validation_decision_report"], "validation decision report")
    for path in (model_path, scores_path, report_path):
        if path.exists() and not overwrite:
            raise IsolationForestValidationError(f"Output already exists; use --overwrite: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    temporary_model = model_path.with_name(model_path.name + ".part")
    temporary_scores = scores_path.with_name(scores_path.name + ".part")
    temporary_report = report_path.with_name(report_path.name + ".part")
    for path in (temporary_model, temporary_scores, temporary_report):
        path.unlink(missing_ok=True)

    connection = duckdb.connect(database=":memory:")
    try:
        feature_names, input_evidence = _validate_upstream_inputs(
            connection,
            feature_path,
            feature_report_path,
            eligibility_path,
            eligibility_report_path,
            parameters_path,
            execution_contract["execution"]["expected_retained_feature_count"],
        )
        train_matrix, validation_matrix, validation_metadata = _load_development_populations(
            connection, feature_path, eligibility_path, feature_names
        )
    finally:
        connection.close()

    if train_matrix.shape[0] != input_evidence["frozen_reference_rows"]:
        raise IsolationForestValidationError("Current eligible training-reference rows differ from the frozen baseline evidence.")

    threshold_quantile = float(comparison_contract["candidate_model"]["alarm_threshold"]["quantile"])
    expected_sampling_seconds = float(execution_contract["execution"]["expected_sampling_seconds"])
    candidate_results: list[dict[str, Any]] = []
    selected_model: IsolationForest | None = None
    selected_scores: np.ndarray | None = None
    selected_alarms: np.ndarray | None = None
    selected_result: dict[str, Any] | None = None

    for candidate in candidates:
        model = build_model(candidate)
        model.fit(train_matrix)
        train_scores = -model.score_samples(train_matrix)
        threshold = float(np.quantile(train_scores, threshold_quantile))
        validation_scores = -model.score_samples(validation_matrix)
        metrics, alarms = candidate_metrics(
            train_scores,
            validation_scores,
            validation_metadata["timestamp"],
            validation_metadata["source_event"],
            validation_metadata["eligible_for_known_event_evaluation"],
            validation_metadata["eligible_for_alarm_burden"],
            threshold,
            expected_sampling_seconds,
        )
        result = {
            "candidate_id": candidate["candidate_id"],
            "complexity_rank": candidate["complexity_rank"],
            "parameters": {
                key: candidate[key]
                for key in (
                    "n_estimators", "max_samples", "max_features", "contamination",
                    "bootstrap", "random_state", "n_jobs",
                )
            },
            "metrics": metrics,
        }
        candidate_results.append(result)
        if selected_result is None or selection_key(result) < selection_key(selected_result):
            selected_result = result
            selected_model = model
            selected_scores = validation_scores.copy()
            selected_alarms = alarms.copy()

    if selected_result is None or selected_model is None or selected_scores is None or selected_alarms is None:
        raise IsolationForestValidationError("Candidate selection produced no frozen winner.")
    candidate_results.sort(key=selection_key)

    try:
        joblib.dump(selected_model, temporary_model, compress=outputs["joblib_compression"])
        _write_selected_scores(
            temporary_scores,
            validation_metadata,
            selected_result["candidate_id"],
            selected_scores,
            selected_alarms,
            outputs["parquet_compression"],
        )
        report = {
            "status": "frozen_after_validation",
            "schema_version": execution_contract["schema_version"],
            "execution_contract": {"path": config_path.as_posix(), "sha256": _sha256(config_path)},
            "comparison_contract": {
                "path": comparison_contract_path.as_posix(),
                "sha256": _sha256(comparison_contract_path),
                "validation_report_path": comparison_report_path.as_posix(),
                "validation_report_sha256": _sha256(comparison_report_path),
                "candidate_count": comparison_report["candidate_boundary"]["candidate_count"],
            },
            "inputs": {
                **input_evidence,
                "eligible_training_reference_rows": int(train_matrix.shape[0]),
                "validation_rows_scored": int(validation_matrix.shape[0]),
                "test_rows_loaded": 0,
                "test_rows_scored": 0,
            },
            "candidate_evaluation": {
                "candidate_count": len(candidate_results),
                "threshold_quantile": threshold_quantile,
                "thresholds_fitted_on_training_only": True,
                "selection_partition": "validation",
                "ranking_order": [item["candidate_id"] for item in candidate_results],
                "candidates": candidate_results,
            },
            "selection": {
                "status": "frozen",
                "rule": comparison_contract["validation_selection"]["rule"],
                "ordered_criteria": comparison_contract["validation_selection"]["ordered_criteria"],
                "selected_candidate": selected_result,
                "selected_model_path": model_path.as_posix(),
                "selected_model_sha256": _sha256(temporary_model),
                "selected_validation_scores_path": scores_path.as_posix(),
                "selected_validation_scores_sha256": _sha256(temporary_scores),
            },
            "governance": {
                "same_frozen_48_feature_set_used_for_every_candidate": True,
                "candidate_models_fitted_on_eligible_training_reference_only": True,
                "candidate_thresholds_fitted_on_training_scores_only": True,
                "candidate_thresholds_frozen_before_validation": True,
                "candidate_selection_used_validation_only": True,
                "baseline_test_evidence_used_for_design_or_selection": False,
                "advanced_test_partition_locked": True,
                "test_rows_loaded": 0,
                "test_rows_scored": 0,
                "unverified_rows_are_verified_healthy": False,
                "alarm_burden_is_false_positive_rate": False,
                "unsupported_classification_metrics_reported": False,
            },
            "software": {
                "python_version": platform.python_version(),
                "duckdb_version": duckdb.__version__,
                "numpy_version": np.__version__,
                "pyarrow_version": pa.__version__,
                "scikit_learn_version": sklearn.__version__,
                "joblib_version": joblib.__version__,
            },
        }
        temporary_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary_model.replace(model_path)
        temporary_scores.replace(scores_path)
        temporary_report.replace(report_path)
    except Exception:
        for path in (temporary_model, temporary_scores, temporary_report):
            path.unlink(missing_ok=True)
        raise
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train, validate, and freeze the governed MetroPT-3 Isolation Forest candidate."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    arguments = build_argument_parser().parse_args()
    try:
        report = run_isolation_forest_validation(arguments.config, overwrite=arguments.overwrite)
    except (IsolationForestValidationError, duckdb.Error, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1
    selected = report["selection"]["selected_candidate"]
    print(
        json.dumps(
            {
                "processing_status": "isolation_forest_validation_completed",
                "candidate_count": report["candidate_evaluation"]["candidate_count"],
                "eligible_training_reference_rows": report["inputs"]["eligible_training_reference_rows"],
                "validation_rows_scored": report["inputs"]["validation_rows_scored"],
                "selected_candidate": selected["candidate_id"],
                "selected_threshold": selected["metrics"]["threshold"],
                "advanced_test_partition_locked": report["governance"]["advanced_test_partition_locked"],
                "test_rows_scored": report["governance"]["test_rows_scored"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

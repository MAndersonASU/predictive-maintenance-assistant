"""One-time held-out test evaluation for the frozen MetroPT-3 Isolation Forest.

This module never fits, refits, tunes, changes features, changes the frozen
threshold, or reselects a candidate. It validates the Day 16 frozen evidence,
loads the selected model artifact, scores eligible test rows exactly once, and
reports transparent comparison evidence against the already-finalized
robust-distance baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import duckdb
import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import sklearn


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "metropt3_isolation_forest_test_evaluation.json"


class IsolationForestTestEvaluationError(ValueError):
    """Raised when a one-time test evaluation would violate governance."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise IsolationForestTestEvaluationError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise IsolationForestTestEvaluationError(f"Invalid {label} JSON: {error}") from error
    if not isinstance(payload, dict):
        raise IsolationForestTestEvaluationError(f"{label} must contain a JSON object.")
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


def _resolve(relative_path: str) -> Path:
    root = PROJECT_ROOT.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise IsolationForestTestEvaluationError(f"Path escapes project root: {relative_path}")
    return candidate


def _quote_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def validate_contract(contract: dict[str, Any]) -> None:
    for section in ("authorization", "inputs", "evaluation", "governance", "outputs"):
        if not isinstance(contract.get(section), dict):
            raise IsolationForestTestEvaluationError(f"Contract section must be an object: {section}")
    if contract.get("schema_version") != 1:
        raise IsolationForestTestEvaluationError("schema_version must be 1.")

    authorization = contract["authorization"]
    if authorization != {
        "one_time_test_evaluation_authorized": True,
        "authorization_scope": "frozen_selected_candidate_only",
        "authorized_candidate_id": "iforest_ne200_ms4096_mf1p0",
        "authorized_threshold": 0.601902290159477,
    }:
        raise IsolationForestTestEvaluationError("The one-time frozen-candidate authorization was changed.")

    expected_inputs = {
        "feature_parquet": "data/processed/metropt3_features.parquet",
        "feature_report": "outputs/metropt3_feature_engineering_report.json",
        "eligibility_parquet": "data/processed/metropt3_baseline_eligibility.parquet",
        "eligibility_report": "outputs/metropt3_baseline_evaluation_contract_report.json",
        "frozen_feature_parameters": "outputs/metropt3_robust_distance_parameters.json",
        "selected_model": "outputs/metropt3_selected_isolation_forest.joblib",
        "validation_report": "outputs/metropt3_isolation_forest_validation_report.json",
        "baseline_test_report": "outputs/metropt3_robust_distance_test_report.json",
    }
    if contract["inputs"] != expected_inputs:
        raise IsolationForestTestEvaluationError("Governed test-evaluation inputs were changed.")

    expected_evaluation = {
        "partition": "test",
        "scoring_eligibility_column": "eligible_for_scoring",
        "known_event_eligibility_column": "eligible_for_known_event_evaluation",
        "alarm_burden_eligibility_column": "eligible_for_alarm_burden",
        "expected_retained_feature_count": 48,
        "expected_sampling_seconds": 10.0,
        "matrix_dtype": "float32",
        "threshold_comparison": "strictly_greater_than",
    }
    if contract["evaluation"] != expected_evaluation:
        raise IsolationForestTestEvaluationError("The frozen test-evaluation rules were changed.")

    governance = contract["governance"]
    required_true = (
        "model_must_be_loaded_without_refit",
        "threshold_must_be_loaded_without_revision",
    )
    required_false = (
        "candidate_reselection_enabled",
        "feature_changes_enabled",
        "test_driven_model_change_enabled",
        "unverified_rows_are_verified_healthy",
        "alarm_burden_is_false_positive_rate",
        "unusualness_is_failure_probability",
        "unsupported_classification_metrics_enabled",
    )
    if any(governance.get(name) is not True for name in required_true):
        raise IsolationForestTestEvaluationError("Frozen-model and frozen-threshold controls are required.")
    if any(governance.get(name) is not False for name in required_false):
        raise IsolationForestTestEvaluationError("A prohibited test-time behavior was enabled.")

    outputs = contract["outputs"]
    if outputs != {
        "test_scores": "data/processed/metropt3_test_isolation_forest.parquet",
        "test_report": "outputs/metropt3_isolation_forest_test_report.json",
        "parquet_compression": "zstd",
    }:
        raise IsolationForestTestEvaluationError("Governed output paths or compression were changed.")


def _validate_frozen_evidence(
    contract: dict[str, Any],
    paths: dict[str, Path],
) -> tuple[list[str], float, dict[str, Any], dict[str, Any]]:
    for label, path in paths.items():
        if not path.is_file():
            raise IsolationForestTestEvaluationError(f"Required input does not exist ({label}): {path}")

    feature_report = _read_json(paths["feature_report"], "Feature report")
    eligibility_report = _read_json(paths["eligibility_report"], "Eligibility report")
    parameters = _read_json(paths["frozen_feature_parameters"], "Frozen feature parameters")
    validation = _read_json(paths["validation_report"], "Isolation Forest validation report")
    baseline = _read_json(paths["baseline_test_report"], "Robust-distance baseline test report")

    if feature_report.get("status") != "valid" or eligibility_report.get("status") != "valid":
        raise IsolationForestTestEvaluationError("Feature and eligibility evidence must both be valid.")
    if feature_report.get("output", {}).get("parquet_sha256") != _sha256(paths["feature_parquet"]):
        raise IsolationForestTestEvaluationError("Feature Parquet SHA-256 does not match its evidence.")
    if eligibility_report.get("output", {}).get("parquet_sha256") != _sha256(paths["eligibility_parquet"]):
        raise IsolationForestTestEvaluationError("Eligibility Parquet SHA-256 does not match its evidence.")

    if validation.get("status") != "frozen_after_validation":
        raise IsolationForestTestEvaluationError("The selected model must be frozen after validation.")
    governance = validation.get("governance", {})
    if governance.get("advanced_test_partition_locked") is not True:
        raise IsolationForestTestEvaluationError("Validation evidence does not show a locked advanced-model test partition.")
    if governance.get("test_rows_loaded") != 0 or governance.get("test_rows_scored") != 0:
        raise IsolationForestTestEvaluationError("Advanced-model test rows were already used before this authorized evaluation.")

    selected = validation.get("selection", {}).get("selected_candidate", {})
    authorized = contract["authorization"]
    if selected.get("candidate_id") != authorized["authorized_candidate_id"]:
        raise IsolationForestTestEvaluationError("Selected candidate does not match the explicit authorization.")
    threshold = selected.get("metrics", {}).get("threshold")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not math.isfinite(float(threshold)):
        raise IsolationForestTestEvaluationError("Frozen threshold is missing or non-finite.")
    if float(threshold) != float(authorized["authorized_threshold"]):
        raise IsolationForestTestEvaluationError("Frozen threshold does not match the explicit authorization.")

    recorded_model_sha = validation.get("selection", {}).get("selected_model_sha256")
    if recorded_model_sha != _sha256(paths["selected_model"]):
        raise IsolationForestTestEvaluationError("Selected model artifact SHA-256 does not match the frozen validation report.")

    retained = parameters.get("retained_features")
    if not isinstance(retained, list):
        raise IsolationForestTestEvaluationError("Frozen feature parameters do not list retained features.")
    feature_names = [item.get("feature") for item in retained if isinstance(item, dict)]
    expected_count = contract["evaluation"]["expected_retained_feature_count"]
    if len(feature_names) != expected_count or len(set(feature_names)) != expected_count or any(not isinstance(x, str) for x in feature_names):
        raise IsolationForestTestEvaluationError(f"Exactly {expected_count} unique frozen features are required.")

    expected_feature_hash = validation.get("inputs", {}).get("retained_feature_names_sha256")
    actual_feature_hash = hashlib.sha256(("\n".join(feature_names) + "\n").encode("utf-8")).hexdigest()
    if expected_feature_hash != actual_feature_hash:
        raise IsolationForestTestEvaluationError("Frozen feature-name identity does not match Day 16 evidence.")

    if baseline.get("status") != "valid":
        raise IsolationForestTestEvaluationError("Finalized robust-distance baseline test evidence is not valid.")
    if baseline.get("governance", {}).get("one_time_test_evaluation_complete") is not True:
        raise IsolationForestTestEvaluationError("Baseline test evaluation is not finalized.")

    return feature_names, float(threshold), validation, baseline


def _score_summary(scores: np.ndarray) -> dict[str, float | int]:
    if scores.ndim != 1 or scores.size == 0 or not np.isfinite(scores).all():
        raise IsolationForestTestEvaluationError("Scores must be a non-empty finite vector.")
    return {
        "row_count": int(scores.size),
        "minimum": float(np.min(scores)),
        "median": float(np.quantile(scores, 0.5)),
        "p95": float(np.quantile(scores, 0.95)),
        "p995": float(np.quantile(scores, 0.995)),
        "maximum": float(np.max(scores)),
    }


def _event_evidence(
    timestamps: np.ndarray,
    events: np.ndarray,
    eligible: np.ndarray,
    alarms: np.ndarray,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    ordered: list[str] = []
    seen: set[str] = set()
    for raw, flag in zip(events, eligible, strict=True):
        if bool(flag):
            event = str(raw)
            if event not in seen:
                seen.add(event)
                ordered.append(event)
    for event in ordered:
        mask = np.asarray([bool(flag) and str(raw) == event for raw, flag in zip(events, eligible, strict=True)])
        event_times = timestamps[mask]
        event_alarms = alarms[mask]
        alarm_indexes = np.flatnonzero(event_alarms)
        first_alarm = None if alarm_indexes.size == 0 else event_times[int(alarm_indexes[0])]
        output.append(
            {
                "source_event": event,
                "event_scored_rows": int(event_times.size),
                "covered": first_alarm is not None,
                "first_alarm_latency_seconds": (
                    None if first_alarm is None else float((first_alarm - event_times[0]) / np.timedelta64(1, "s"))
                ),
                "alarm_rows_within_documented_event": int(np.count_nonzero(event_alarms)),
            }
        )
    return output


def _comparison_summary(
    advanced_metrics: dict[str, Any],
    baseline_report: dict[str, Any],
) -> dict[str, Any]:
    baseline_test = baseline_report["test"]
    return {
        "purpose": "held_out_evidence_comparison_not_model_reselection",
        "isolation_forest": {
            "documented_event_coverage_fraction": advanced_metrics["documented_event_coverage_fraction"],
            "mean_first_alarm_latency_seconds_for_covered_events": advanced_metrics[
                "mean_first_alarm_latency_seconds_for_covered_events"
            ],
            "alarms_per_24_observed_hours": advanced_metrics["alarms_per_24_observed_hours"],
        },
        "robust_distance_baseline": {
            "documented_event_coverage_fraction": baseline_test.get("documented_event_coverage_fraction"),
            "mean_first_alarm_latency_seconds_for_covered_events": _baseline_mean_latency(baseline_test),
            "alarms_per_24_observed_hours": baseline_test.get("alarms_per_24_observed_hours"),
        },
        "test_evidence_used_for_refit": False,
        "test_evidence_used_for_threshold_change": False,
        "test_evidence_used_for_feature_change": False,
        "test_evidence_used_for_candidate_reselection": False,
    }


def _baseline_mean_latency(baseline_test: dict[str, Any]) -> float | None:
    values = [
        item.get("first_alarm_latency_seconds")
        for item in baseline_test.get("documented_event_evidence", [])
        if item.get("covered") and item.get("first_alarm_latency_seconds") is not None
    ]
    return None if not values else float(np.mean(np.asarray(values, dtype=float)))


def run_test_evaluation(config_path: Path) -> dict[str, Any]:
    contract = _read_json(config_path, "Isolation Forest test-evaluation contract")
    validate_contract(contract)
    input_paths = {name: _resolve(value) for name, value in contract["inputs"].items()}
    output_scores = _resolve(contract["outputs"]["test_scores"])
    output_report = _resolve(contract["outputs"]["test_report"])

    # Strict one-time lock: a completed output is never silently overwritten.
    for path in (output_scores, output_report):
        if path.exists():
            raise IsolationForestTestEvaluationError(
                f"One-time test output already exists; do not rerun or overwrite it: {path}"
            )

    feature_names, threshold, validation, baseline = _validate_frozen_evidence(contract, input_paths)
    model = joblib.load(input_paths["selected_model"])
    if not hasattr(model, "score_samples"):
        raise IsolationForestTestEvaluationError("Frozen model artifact does not expose score_samples().")
    if hasattr(model, "n_features_in_") and int(model.n_features_in_) != len(feature_names):
        raise IsolationForestTestEvaluationError("Frozen model feature count does not match the frozen feature set.")

    connection = duckdb.connect(database=":memory:")
    try:
        feature_source = f"read_parquet({_quote_literal(input_paths['feature_parquet'])})"
        eligibility_source = f"read_parquet({_quote_literal(input_paths['eligibility_parquet'])})"
        feature_sql = ", ".join(
            f"CAST(f.{_quote_identifier(name)} AS FLOAT) AS {_quote_identifier(name)}"
            for name in feature_names
        )
        query = f"""
            SELECT
                f.timestamp,
                f.segment_id,
                f.partition,
                f.target_state,
                f.source_event,
                e.eligible_for_known_event_evaluation,
                e.eligible_for_alarm_burden,
                {feature_sql}
            FROM {feature_source} f
            INNER JOIN {eligibility_source} e USING (timestamp)
            WHERE f.partition = 'test'
              AND e.partition = 'test'
              AND e.eligible_for_scoring
            ORDER BY f.timestamp
        """
        columns = connection.execute(query).fetchnumpy()
    finally:
        connection.close()

    if len(columns.get("timestamp", [])) == 0:
        raise IsolationForestTestEvaluationError("The eligible test scoring population is empty.")
    if set(np.unique(columns["partition"])) != {"test"}:
        raise IsolationForestTestEvaluationError("A non-test row entered the advanced-model scoring population.")

    matrix = np.column_stack([np.asarray(columns[name], dtype=np.float32) for name in feature_names])
    if matrix.ndim != 2 or matrix.shape[1] != len(feature_names) or not np.isfinite(matrix).all():
        raise IsolationForestTestEvaluationError("Test matrix is invalid or contains non-finite frozen features.")

    scores = -np.asarray(model.score_samples(matrix), dtype=np.float64)
    alarms = scores > threshold
    events = _event_evidence(
        columns["timestamp"],
        columns["source_event"],
        columns["eligible_for_known_event_evaluation"],
        alarms,
    )
    latencies = [item["first_alarm_latency_seconds"] for item in events if item["covered"]]
    burden_flags = np.asarray(columns["eligible_for_alarm_burden"], dtype=bool)
    burden_rows = int(np.count_nonzero(burden_flags))
    burden_alarms = int(np.count_nonzero(alarms & burden_flags))
    observed_hours = burden_rows * float(contract["evaluation"]["expected_sampling_seconds"]) / 3600.0
    covered = sum(1 for item in events if item["covered"])

    advanced_metrics = {
        "scored_rows": int(scores.size),
        "score_summary": _score_summary(scores),
        "documented_event_count": len(events),
        "documented_events_covered": covered,
        "documented_event_coverage_fraction": None if not events else covered / len(events),
        "mean_first_alarm_latency_seconds_for_covered_events": None if not latencies else float(np.mean(latencies)),
        "documented_event_evidence": events,
        "unlabeled_alarm_burden_rows": burden_rows,
        "unlabeled_alarm_count": burden_alarms,
        "alarm_burden_fraction": None if burden_rows == 0 else burden_alarms / burden_rows,
        "alarms_per_24_observed_hours": None if observed_hours == 0 else burden_alarms * 24.0 / observed_hours,
    }

    output_scores.parent.mkdir(parents=True, exist_ok=True)
    temporary_scores = output_scores.with_name(output_scores.name + ".part")
    temporary_scores.unlink(missing_ok=True)
    try:
        table = pa.table(
            {
                "timestamp": pa.array(columns["timestamp"]),
                "segment_id": pa.array(columns["segment_id"]),
                "partition": pa.array(columns["partition"]),
                "target_state": pa.array(columns["target_state"]),
                "source_event": pa.array(columns["source_event"]),
                "eligible_for_known_event_evaluation": pa.array(columns["eligible_for_known_event_evaluation"]),
                "eligible_for_alarm_burden": pa.array(columns["eligible_for_alarm_burden"]),
                "candidate_id": pa.array(
                    [contract["authorization"]["authorized_candidate_id"]] * len(scores),
                    type=pa.string(),
                ),
                "isolation_forest_score": pa.array(scores, type=pa.float64()),
                "alarm": pa.array(alarms, type=pa.bool_()),
            }
        )
        pq.write_table(table, temporary_scores, compression=contract["outputs"]["parquet_compression"])
        temporary_scores.replace(output_scores)
    except Exception:
        temporary_scores.unlink(missing_ok=True)
        raise

    report = {
        "status": "frozen_after_one_time_test_evaluation",
        "schema_version": contract["schema_version"],
        "authorization": {
            **contract["authorization"],
            "test_access_consumed": True,
        },
        "contract": {"path": config_path.as_posix(), "sha256": _sha256(config_path)},
        "frozen_model": {
            "candidate_id": contract["authorization"]["authorized_candidate_id"],
            "threshold": threshold,
            "model_sha256": _sha256(input_paths["selected_model"]),
            "retained_feature_count": len(feature_names),
            "loaded_without_refit": True,
            "threshold_loaded_without_revision": True,
        },
        "advanced_model_test": {
            **advanced_metrics,
            "scores_path": output_scores.as_posix(),
            "scores_sha256": _sha256(output_scores),
        },
        "baseline_comparison": _comparison_summary(advanced_metrics, baseline),
        "release_decision": {
            "status": "machine_learning_decision_frozen_after_test_reporting",
            "advanced_model_candidate": contract["authorization"]["authorized_candidate_id"],
            "transparent_baseline": "maximum_absolute_robust_z_score",
            "candidate_reselected_from_test_results": False,
            "model_refit_from_test_results": False,
            "threshold_changed_from_test_results": False,
            "feature_set_changed_from_test_results": False,
            "interpretation": (
                "Held-out test evidence is final reporting evidence. It does not authorize "
                "model reselection, refitting, feature changes, or threshold changes."
            ),
        },
        "governance": {
            "training_rows_scored": 0,
            "validation_rows_scored": 0,
            "only_eligible_test_rows_scored": True,
            "model_fitted_during_test_evaluation": False,
            "threshold_revised_using_test_evidence": False,
            "features_changed_using_test_evidence": False,
            "candidate_reselected_using_test_evidence": False,
            "unverified_rows_are_verified_healthy": False,
            "alarm_burden_is_false_positive_rate": False,
            "unusualness_is_failure_probability": False,
            "unsupported_classification_metrics_reported": False,
            "one_time_advanced_model_test_evaluation_complete": True,
        },
        "limitations": [
            "Unverified operational rows are not verified healthy negatives.",
            "Alarm burden is not a false-positive rate.",
            "Isolation Forest unusualness scores are not failure probabilities.",
            "Documented-event coverage is limited to governed events present in the locked test partition.",
            "The held-out test comparison is reporting evidence, not permission to tune or reselect a model.",
        ],
        "software": {
            "python_version": platform.python_version(),
            "duckdb_version": duckdb.__version__,
            "numpy_version": np.__version__,
            "pyarrow_version": pa.__version__,
            "scikit_learn_version": sklearn.__version__,
            "joblib_version": joblib.__version__,
        },
    }
    _write_json_atomic(report, output_report)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the separately authorized one-time test evaluation of the frozen Isolation Forest."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    return parser


def main() -> int:
    arguments = build_argument_parser().parse_args()
    try:
        report = run_test_evaluation(arguments.config)
    except (IsolationForestTestEvaluationError, duckdb.Error, OSError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1
    advanced = report["advanced_model_test"]
    print(
        json.dumps(
            {
                "processing_status": "isolation_forest_one_time_test_evaluation_completed",
                "candidate_id": report["frozen_model"]["candidate_id"],
                "threshold": report["frozen_model"]["threshold"],
                "test_scored_rows": advanced["scored_rows"],
                "documented_event_count": advanced["documented_event_count"],
                "documented_events_covered": advanced["documented_events_covered"],
                "alarms_per_24_observed_hours": advanced["alarms_per_24_observed_hours"],
                "candidate_reselected_using_test_evidence": report["governance"][
                    "candidate_reselected_using_test_evidence"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

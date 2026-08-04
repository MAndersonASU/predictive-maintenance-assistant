"""Diagnose a frozen robust-distance baseline without using test data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "metropt3_robust_distance_diagnosis.json"


class RobustDistanceDiagnosisError(ValueError):
    """Raised when diagnosis inputs or controls violate governance."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise RobustDistanceDiagnosisError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RobustDistanceDiagnosisError(f"Invalid {label} JSON: {error}") from error
    if not isinstance(payload, dict):
        raise RobustDistanceDiagnosisError(f"{label} must contain a JSON object.")
    return payload


def validate_contract(contract: dict[str, Any]) -> None:
    for section in ("inputs", "diagnosis", "governance", "outputs"):
        if not isinstance(contract.get(section), dict):
            raise RobustDistanceDiagnosisError(f"Contract section must be an object: {section}")
    governance = contract["governance"]
    required_true = (
        "parameters_must_be_frozen", "threshold_candidates_training_derived_only",
        "validation_only_diagnosis", "test_partition_locked",
    )
    if any(governance.get(name) is not True for name in required_true):
        raise RobustDistanceDiagnosisError("Frozen-parameter, training-threshold, validation-only, and test-lock controls are required.")
    if governance.get("unverified_rows_are_verified_healthy") is not False:
        raise RobustDistanceDiagnosisError("Unverified rows cannot be represented as verified healthy.")
    if governance.get("alarm_burden_is_false_positive_rate") is not False:
        raise RobustDistanceDiagnosisError("Alarm burden cannot be represented as false-positive rate.")
    diagnosis = contract["diagnosis"]
    quantiles = diagnosis.get("threshold_quantiles")
    if not isinstance(quantiles, list) or not 1 <= len(quantiles) <= 5:
        raise RobustDistanceDiagnosisError("Provide one to five bounded threshold quantiles.")
    if any(isinstance(q, bool) or not isinstance(q, (int, float)) or not 0 < q < 1 for q in quantiles):
        raise RobustDistanceDiagnosisError("Every threshold quantile must be between zero and one.")
    if diagnosis.get("selected_threshold_quantile") not in quantiles:
        raise RobustDistanceDiagnosisError("The selected quantile must be one of the bounded candidates.")
    state_features = diagnosis.get("operating_state_features")
    if (
        not isinstance(state_features, list)
        or not state_features
        or any(not isinstance(name, str) or not name for name in state_features)
        or len(state_features) != len(set(state_features))
    ):
        raise RobustDistanceDiagnosisError("Operating-state features must be a non-empty ordered list of unique names.")
    state_limit = diagnosis.get("top_operating_state_count")
    if isinstance(state_limit, bool) or not isinstance(state_limit, int) or state_limit < 1:
        raise RobustDistanceDiagnosisError("Top operating-state count must be a positive integer.")


def _resolve(value: str) -> Path:
    return PROJECT_ROOT / value


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


def _contribution_expression(parameters: list[dict[str, Any]]) -> str:
    terms = []
    for item in parameters:
        feature, median, iqr = item.get("feature"), item.get("median"), item.get("iqr")
        if not isinstance(feature, str) or not feature or not isinstance(median, (int, float)):
            raise RobustDistanceDiagnosisError("Every frozen feature requires a name and numeric median.")
        if not isinstance(iqr, (int, float)) or not math.isfinite(float(iqr)) or float(iqr) <= 0:
            raise RobustDistanceDiagnosisError(f"Frozen IQR must be positive: {feature}")
        terms.append(
            f"struct_pack(feature := {_quote_literal(feature)}, contribution := "
            f"abs(({_quote_identifier(feature)} - {float(median)!r}) / {float(iqr)!r}))"
        )
    if not terms:
        raise RobustDistanceDiagnosisError("At least one frozen retained feature is required.")
    return "list_value(" + ", ".join(terms) + ")"


def _validate_frozen_inputs(parameters: dict[str, Any], report: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
    if parameters.get("status") != "frozen_before_validation" or parameters.get("test_partition_used") is not False:
        raise RobustDistanceDiagnosisError("Parameters must be frozen before validation and must not use test data.")
    if report.get("status") != "valid" or report.get("governance", {}).get("test_rows_scored") != 0:
        raise RobustDistanceDiagnosisError("Validation evidence must be valid with zero test rows scored.")
    retained = parameters.get("retained_features")
    threshold = parameters.get("threshold")
    if not isinstance(retained, list) or not isinstance(threshold, (int, float)):
        raise RobustDistanceDiagnosisError("Frozen parameters are missing retained features or threshold.")
    return retained, float(threshold)


def run_diagnosis(config_path: Path, *, overwrite: bool = False) -> dict[str, Any]:
    contract = _read_json(config_path, "Diagnostic contract")
    validate_contract(contract)
    paths = {name: _resolve(value) for name, value in contract["inputs"].items()}
    output_path = _resolve(contract["outputs"]["report"])
    if output_path.exists() and not overwrite:
        raise RobustDistanceDiagnosisError(f"Output already exists; use --overwrite: {output_path}")
    for name, path in paths.items():
        if not path.is_file():
            raise RobustDistanceDiagnosisError(f"Input does not exist ({name}): {path}")
    parameters = _read_json(paths["frozen_parameters"], "Frozen parameters")
    validation_report = _read_json(paths["validation_report"], "Validation report")
    retained, frozen_threshold = _validate_frozen_inputs(parameters, validation_report)
    expression = _contribution_expression(retained)
    feature_source = f"read_parquet({_quote_literal(paths['feature_parquet'])})"
    eligibility_source = f"read_parquet({_quote_literal(paths['eligibility_parquet'])})"
    score_source = f"read_parquet({_quote_literal(paths['validation_scores'])})"
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute(f"""
            CREATE TEMP VIEW diagnostic_rows AS
            SELECT f.*, e.eligible_for_reference_fit, e.eligible_for_scoring,
                   e.eligible_for_known_event_evaluation, e.eligible_for_alarm_burden,
                   coalesce(
                       s.robust_distance_score,
                       list_reduce({expression}, (best, item) ->
                           CASE WHEN item.contribution > best.contribution THEN item ELSE best END
                       ).contribution
                   ) AS robust_distance_score,
                   s.alarm,
                   list_reduce({expression}, (best, item) ->
                       CASE WHEN item.contribution > best.contribution THEN item ELSE best END
                   ) AS dominant
            FROM {feature_source} f
            JOIN {eligibility_source} e USING (timestamp)
            LEFT JOIN {score_source} s USING (timestamp)
            WHERE f.partition IN ('train', 'validation')
        """)
        test_rows = int(connection.execute("SELECT count(*) FROM diagnostic_rows WHERE partition = 'test'").fetchone()[0])
        if test_rows:
            raise RobustDistanceDiagnosisError("Test rows entered the diagnostic population.")
        training_rows = int(connection.execute("SELECT count(*) FROM diagnostic_rows WHERE partition='train' AND eligible_for_reference_fit").fetchone()[0])
        validation_rows = int(connection.execute("SELECT count(*) FROM diagnostic_rows WHERE partition='validation' AND eligible_for_scoring").fetchone()[0])
        if training_rows == 0 or validation_rows == 0:
            raise RobustDistanceDiagnosisError("Training-reference and validation scoring populations must be non-empty.")
        candidates = []
        for quantile in contract["diagnosis"]["threshold_quantiles"]:
            threshold = float(connection.execute(
                "SELECT quantile_cont(robust_distance_score, ?) FROM diagnostic_rows "
                "WHERE partition='train' AND eligible_for_reference_fit", [quantile]
            ).fetchone()[0])
            burden_rows, alarms = connection.execute(
                "SELECT count(*), count(*) FILTER (WHERE robust_distance_score > ?) "
                "FROM diagnostic_rows WHERE partition='validation' AND eligible_for_alarm_burden",
                [threshold],
            ).fetchone()
            event_rows = connection.execute(
                "SELECT source_event, min(timestamp), min(timestamp) FILTER (WHERE robust_distance_score > ?) "
                "FROM diagnostic_rows WHERE partition='validation' AND eligible_for_known_event_evaluation "
                "GROUP BY source_event ORDER BY min(timestamp)", [threshold]
            ).fetchall()
            candidates.append({
                "quantile": float(quantile), "training_derived_threshold": threshold,
                "validation_alarm_burden_rows": int(burden_rows), "validation_alarm_count": int(alarms),
                "validation_alarm_burden_fraction": None if not burden_rows else int(alarms) / int(burden_rows),
                "documented_events": [{
                    "source_event": str(event), "covered": first_alarm is not None,
                    "first_alarm_latency_seconds": None if first_alarm is None else (first_alarm - start).total_seconds(),
                } for event, start, first_alarm in event_rows],
            })
        dominant_rows = connection.execute("""
            SELECT dominant.feature, count(*) AS rows, count(*) FILTER (WHERE alarm) AS alarm_rows,
                   max(dominant.contribution) AS maximum_contribution
            FROM diagnostic_rows WHERE partition='validation' AND eligible_for_scoring
            GROUP BY dominant.feature ORDER BY alarm_rows DESC, rows DESC, dominant.feature
            LIMIT ?
        """, [contract["diagnosis"]["top_feature_count"]]).fetchall()
        segments = connection.execute("""
            SELECT segment_id, count(*) AS rows, count(*) FILTER (WHERE alarm) AS alarms,
                   count(*) FILTER (WHERE eligible_for_alarm_burden) AS burden_rows
            FROM diagnostic_rows WHERE partition='validation' AND eligible_for_scoring
            GROUP BY segment_id ORDER BY alarms DESC, segment_id LIMIT ?
        """, [contract["diagnosis"]["top_segment_count"]]).fetchall()
        time_rows = connection.execute("""
            SELECT extract(hour FROM timestamp) AS hour_utc, count(*) AS rows,
                   count(*) FILTER (WHERE alarm) AS alarms
            FROM diagnostic_rows WHERE partition='validation' AND eligible_for_scoring
            GROUP BY hour_utc ORDER BY hour_utc
        """).fetchall()
        state_features = contract["diagnosis"]["operating_state_features"]
        state_columns = ", ".join(_quote_identifier(name) for name in state_features)
        state_rows = connection.execute(f"""
            SELECT {state_columns}, count(*) AS scored_rows,
                   count(*) FILTER (WHERE eligible_for_alarm_burden) AS burden_rows,
                   count(*) FILTER (WHERE eligible_for_alarm_burden AND alarm) AS alarm_rows
            FROM diagnostic_rows
            WHERE partition='validation' AND eligible_for_scoring
            GROUP BY {state_columns}
            ORDER BY alarm_rows DESC, burden_rows DESC, {state_columns}
            LIMIT ?
        """, [contract["diagnosis"]["top_operating_state_count"]]).fetchall()
    finally:
        connection.close()
    iqrs = sorted(float(item["iqr"]) for item in retained)
    ratio_limit = float(contract["diagnosis"]["small_iqr_ratio_limit"])
    small_cutoff = iqrs[-1] * ratio_limit
    state_feature_count = len(state_features)
    report = {
        "status": "valid",
        "schema_version": contract["schema_version"],
        "inputs": {name: {"path": path.as_posix(), "sha256": _sha256(path)} for name, path in paths.items()},
        "population": {"training_reference_rows": training_rows, "validation_scored_rows": validation_rows, "test_rows": 0},
        "frozen_baseline": {"threshold": frozen_threshold, "retained_feature_count": len(retained)},
        "small_nonzero_iqr": {
            "relative_to_largest_iqr_limit": ratio_limit, "cutoff": small_cutoff,
            "features": [{"feature": item["feature"], "iqr": item["iqr"]} for item in retained if float(item["iqr"]) <= small_cutoff],
        },
        "dominant_validation_features": [{"feature": a, "dominant_rows": int(b), "alarm_rows": int(c), "maximum_contribution": float(d)} for a, b, c, d in dominant_rows],
        "alarm_concentration_by_segment": [{"segment_id": int(a), "scored_rows": int(b), "alarm_rows": int(c), "unlabeled_burden_rows": int(d)} for a, b, c, d in segments],
        "alarm_concentration_by_hour_utc": [{"hour": int(a), "scored_rows": int(b), "alarm_rows": int(c)} for a, b, c in time_rows],
        "alarm_concentration_by_operating_state": [
            {
                "state": {name: float(row[index]) for index, name in enumerate(state_features)},
                "scored_rows": int(row[state_feature_count]),
                "unlabeled_burden_rows": int(row[state_feature_count + 1]),
                "alarm_rows": int(row[state_feature_count + 2]),
                "alarm_burden_fraction": None if not row[state_feature_count + 1] else int(row[state_feature_count + 2]) / int(row[state_feature_count + 1]),
            }
            for row in state_rows
        ],
        "training_derived_threshold_candidates": candidates,
        "decision": {
            "selected_threshold_quantile": contract["diagnosis"]["selected_threshold_quantile"],
            "baseline_family": "maximum_absolute_robust_z_score",
            "test_partition_remains_locked": True,
            "decision_status": "frozen_after_validation_diagnosis",
        },
        "limitations": [
            "Unverified operational rows are not verified healthy negatives.",
            "Alarm burden is not a false-positive rate.",
            "Operating-state burden fractions based on very small row counts are unstable and must not be interpreted as reliable state-risk estimates.",
            "The diagnosis does not estimate failure probability.",
        ],
    }
    _write_json_atomic(report, output_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose the frozen MetroPT-3 robust-distance baseline.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()
    try:
        report = run_diagnosis(arguments.config, overwrite=arguments.overwrite)
    except (RobustDistanceDiagnosisError, duckdb.Error, OSError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps({"processing_status": "robust_distance_diagnosis_completed", **report["population"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

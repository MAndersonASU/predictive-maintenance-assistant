"""Fit and validate a transparent MetroPT-3 robust-distance baseline.

All learned values come from eligible training-reference rows. The frozen
parameters and threshold are applied to validation only; test rows are never
read into the scoring population.
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


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "metropt3_robust_distance.json"
GOVERNANCE_COLUMNS = {
    "timestamp", "segment_id", "partition", "target_state", "binary_target",
    "source_event", "exclusion_reason", "history_group_id",
    "history_rows_available", "has_lag_1_history", "has_full_6_row_history",
    "has_full_30_row_history",
}


class RobustDistanceError(ValueError):
    """Raised when the robust-distance workflow would violate governance."""


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
        raise RobustDistanceError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RobustDistanceError(f"Invalid {label} JSON: {error}") from error
    if not isinstance(payload, dict):
        raise RobustDistanceError(f"{label} must contain a JSON object.")
    return payload


def validate_contract(contract: dict[str, Any]) -> None:
    """Reject unsafe fit, threshold, validation, or test controls."""
    for section in ("dataset", "fit", "score", "validation", "outputs"):
        if not isinstance(contract.get(section), dict):
            raise RobustDistanceError(f"Contract section must be an object: {section}")
    fit, score, validation = contract["fit"], contract["score"], contract["validation"]
    if fit.get("partition") != "train" or fit.get("eligibility_column") != "eligible_for_reference_fit":
        raise RobustDistanceError("Robust parameters must fit eligible training-reference rows only.")
    if fit.get("location") != "median" or fit.get("scale") != "interquartile_range":
        raise RobustDistanceError("The governed location and scale are median and IQR.")
    if fit.get("zero_iqr_policy") != "exclude_feature_and_record_reason":
        raise RobustDistanceError("Zero-IQR features must be excluded and recorded.")
    quantile = score.get("threshold_quantile")
    if isinstance(quantile, bool) or not isinstance(quantile, (int, float)) or not 0 < quantile < 1:
        raise RobustDistanceError("Threshold quantile must be between zero and one.")
    if score.get("threshold_fit_population") != "eligible_training_reference_scores":
        raise RobustDistanceError("Threshold fitting must use eligible training-reference scores only.")
    if score.get("threshold_frozen_before_validation") is not True:
        raise RobustDistanceError("The training-derived threshold must be frozen before validation.")
    if validation.get("partition") != "validation" or validation.get("test_partition_locked") is not True:
        raise RobustDistanceError("Validation must run before test and the test partition must remain locked.")


def load_contract(path: Path) -> dict[str, Any]:
    contract = _read_json(path, "Robust-distance contract")
    validate_contract(contract)
    return contract


def _resolve(path_value: str) -> Path:
    return PROJECT_ROOT / path_value


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


def _model_features(connection: duckdb.DuckDBPyConnection, feature_path: Path) -> list[str]:
    rows = connection.execute(
        f"DESCRIBE SELECT * FROM read_parquet({_quote_literal(feature_path)})"
    ).fetchall()
    numeric_types = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "FLOAT", "DOUBLE", "DECIMAL", "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT")
    return [
        str(name) for name, data_type, *_ in rows
        if str(name) not in GOVERNANCE_COLUMNS and str(data_type).upper().startswith(numeric_types)
    ]


def _validate_inputs(
    connection: duckdb.DuckDBPyConnection,
    feature_path: Path,
    feature_report_path: Path,
    eligibility_path: Path,
    eligibility_report_path: Path,
) -> dict[str, Any]:
    for path, label in ((feature_path, "Feature Parquet"), (eligibility_path, "Eligibility Parquet")):
        if not path.is_file():
            raise RobustDistanceError(f"{label} does not exist: {path}")
    feature_report = _read_json(feature_report_path, "Feature evidence")
    eligibility_report = _read_json(eligibility_report_path, "Eligibility evidence")
    if feature_report.get("status") != "valid" or eligibility_report.get("status") != "valid":
        raise RobustDistanceError("Upstream feature and eligibility evidence must both be valid.")
    feature_sha, eligibility_sha = _sha256(feature_path), _sha256(eligibility_path)
    if feature_report.get("output", {}).get("parquet_sha256") != feature_sha:
        raise RobustDistanceError("Feature Parquet SHA-256 does not match its evidence report.")
    if eligibility_report.get("output", {}).get("parquet_sha256") != eligibility_sha:
        raise RobustDistanceError("Eligibility Parquet SHA-256 does not match its evidence report.")
    feature_count = int(connection.execute(
        f"SELECT count(*) FROM read_parquet({_quote_literal(feature_path)})"
    ).fetchone()[0])
    eligibility_count = int(connection.execute(
        f"SELECT count(*) FROM read_parquet({_quote_literal(eligibility_path)})"
    ).fetchone()[0])
    if feature_count == 0 or feature_count != eligibility_count:
        raise RobustDistanceError("Feature and eligibility inputs must contain the same non-empty row count.")
    mismatch = int(connection.execute(f"""
        SELECT count(*) FROM
        read_parquet({_quote_literal(feature_path)}) f
        FULL OUTER JOIN read_parquet({_quote_literal(eligibility_path)}) e USING (timestamp)
        WHERE f.timestamp IS NULL OR e.timestamp IS NULL
    """).fetchone()[0])
    if mismatch:
        raise RobustDistanceError("Feature and eligibility timestamps do not match.")
    return {
        "row_count": feature_count,
        "feature_parquet_sha256": feature_sha,
        "eligibility_parquet_sha256": eligibility_sha,
    }


def _fit_parameters(
    connection: duckdb.DuckDBPyConnection,
    feature_path: Path,
    eligibility_path: Path,
    features: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    connection.execute(f"""
        CREATE OR REPLACE TEMP VIEW joined_inputs AS
        SELECT f.*, e.eligible_for_reference_fit, e.eligible_for_scoring,
               e.eligible_for_known_event_evaluation, e.eligible_for_alarm_burden
        FROM read_parquet({_quote_literal(feature_path)}) f
        INNER JOIN read_parquet({_quote_literal(eligibility_path)}) e USING (timestamp)
    """)
    reference_rows = int(connection.execute(
        "SELECT count(*) FROM joined_inputs WHERE eligible_for_reference_fit AND partition = 'train'"
    ).fetchone()[0])
    leaked_fit_rows = int(connection.execute(
        "SELECT count(*) FROM joined_inputs WHERE eligible_for_reference_fit AND partition != 'train'"
    ).fetchone()[0])
    if reference_rows == 0 or leaked_fit_rows:
        raise RobustDistanceError("Reference fitting population must be non-empty and training-only.")
    retained, excluded = [], []
    for feature in features:
        name = _quote_identifier(feature)
        q25, median, q75, nulls = connection.execute(f"""
            SELECT quantile_cont({name}, 0.25), median({name}), quantile_cont({name}, 0.75),
                   count(*) FILTER (WHERE {name} IS NULL)
            FROM joined_inputs WHERE eligible_for_reference_fit AND partition = 'train'
        """).fetchone()
        if nulls:
            raise RobustDistanceError(f"Eligible reference feature contains nulls: {feature}")
        iqr = float(q75) - float(q25)
        if not math.isfinite(iqr) or iqr < 0:
            raise RobustDistanceError(f"Invalid IQR for feature: {feature}")
        if iqr == 0:
            excluded.append({"feature": feature, "reason": "zero_iqr_in_eligible_training_reference"})
        else:
            retained.append({"feature": feature, "median": float(median), "iqr": iqr})
    if not retained:
        raise RobustDistanceError("No non-zero-IQR model features remain.")
    return retained, excluded, reference_rows


def _score_expression(parameters: list[dict[str, Any]]) -> str:
    terms = [
        f"abs(({_quote_identifier(item['feature'])} - {item['median']!r}) / {item['iqr']!r})"
        for item in parameters
    ]
    return "greatest(" + ", ".join(terms) + ")"


def _summary(connection: duckdb.DuckDBPyConnection, view: str, condition: str) -> dict[str, float | int | None]:
    row = connection.execute(f"""
        SELECT count(*), min(robust_distance_score), quantile_cont(robust_distance_score, 0.5),
               quantile_cont(robust_distance_score, 0.95), quantile_cont(robust_distance_score, 0.995),
               max(robust_distance_score)
        FROM {view} WHERE {condition}
    """).fetchone()
    names = ("row_count", "minimum", "median", "p95", "p995", "maximum")
    return {name: (int(value) if name == "row_count" else (None if value is None else float(value))) for name, value in zip(names, row)}


def run_robust_distance(
    config_path: Path,
    *,
    feature_path: Path | None = None,
    feature_report_path: Path | None = None,
    eligibility_path: Path | None = None,
    eligibility_report_path: Path | None = None,
    parameters_path: Path | None = None,
    scores_path: Path | None = None,
    report_path: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fit on eligible training rows and report validation-only evidence."""
    contract = load_contract(config_path)
    dataset, outputs = contract["dataset"], contract["outputs"]
    feature_path = feature_path or _resolve(dataset["feature_parquet_path"])
    feature_report_path = feature_report_path or _resolve(dataset["feature_evidence_path"])
    eligibility_path = eligibility_path or _resolve(dataset["eligibility_parquet_path"])
    eligibility_report_path = eligibility_report_path or _resolve(dataset["eligibility_evidence_path"])
    parameters_path = parameters_path or _resolve(outputs["parameters"])
    scores_path = scores_path or _resolve(outputs["validation_scores"])
    report_path = report_path or _resolve(outputs["report"])
    for path in (parameters_path, scores_path, report_path):
        if path.exists() and not overwrite:
            raise RobustDistanceError(f"Output already exists; use --overwrite: {path}")

    connection = duckdb.connect(database=":memory:")
    temporary_scores = scores_path.with_name(scores_path.name + ".part")
    try:
        inputs = _validate_inputs(connection, feature_path, feature_report_path, eligibility_path, eligibility_report_path)
        features = _model_features(connection, feature_path)
        parameters, excluded, reference_rows = _fit_parameters(connection, feature_path, eligibility_path, features)
        expression = _score_expression(parameters)
        connection.execute(f"""
            CREATE OR REPLACE TEMP VIEW training_scores AS
            SELECT timestamp, {expression} AS robust_distance_score
            FROM joined_inputs
            WHERE eligible_for_reference_fit AND partition = 'train'
        """)
        threshold = float(connection.execute(
            f"SELECT quantile_cont(robust_distance_score, {contract['score']['threshold_quantile']!r}) FROM training_scores"
        ).fetchone()[0])
        connection.execute(f"""
            CREATE OR REPLACE TEMP VIEW validation_scores AS
            SELECT timestamp, segment_id, partition, target_state, source_event,
                   eligible_for_known_event_evaluation, eligible_for_alarm_burden,
                   {expression} AS robust_distance_score,
                   {expression} > {threshold!r} AS alarm
            FROM joined_inputs
            WHERE partition = 'validation' AND eligible_for_scoring
            ORDER BY timestamp
        """)
        test_rows_scored = int(connection.execute(
            "SELECT count(*) FROM validation_scores WHERE partition = 'test'"
        ).fetchone()[0])
        validation_rows = int(connection.execute("SELECT count(*) FROM validation_scores").fetchone()[0])
        if validation_rows == 0 or test_rows_scored:
            raise RobustDistanceError("Validation scoring population is empty or test locking failed.")
        event_rows = connection.execute("""
            SELECT source_event, min(timestamp), min(timestamp) FILTER (WHERE alarm),
                   count(*) FILTER (WHERE alarm)
            FROM validation_scores
            WHERE eligible_for_known_event_evaluation
            GROUP BY source_event ORDER BY min(timestamp)
        """).fetchall()
        event_evidence = []
        for event, start, first_alarm, alarm_rows in event_rows:
            event_evidence.append({
                "source_event": str(event),
                "covered": first_alarm is not None,
                "first_alarm_latency_seconds": None if first_alarm is None else (first_alarm - start).total_seconds(),
                "alarm_rows_within_documented_event": int(alarm_rows),
            })
        burden_rows, burden_alarms = connection.execute("""
            SELECT count(*), count(*) FILTER (WHERE alarm)
            FROM validation_scores WHERE eligible_for_alarm_burden
        """).fetchone()
        sampling = float(contract["validation"]["expected_sampling_seconds"])
        observed_hours = int(burden_rows) * sampling / 3600.0
        temporary_scores.parent.mkdir(parents=True, exist_ok=True)
        temporary_scores.unlink(missing_ok=True)
        connection.execute(
            f"COPY validation_scores TO {_quote_literal(temporary_scores)} "
            f"(FORMAT PARQUET, COMPRESSION {_quote_literal(outputs['compression'])})"
        )
        temporary_scores.replace(scores_path)
        train_summary = _summary(connection, "training_scores", "true")
        validation_summary = _summary(connection, "validation_scores", "true")
    except Exception:
        temporary_scores.unlink(missing_ok=True)
        raise
    finally:
        connection.close()

    parameter_payload = {
        "status": "frozen_before_validation",
        "fit_partition": "train",
        "eligible_reference_rows": reference_rows,
        "threshold_quantile": contract["score"]["threshold_quantile"],
        "threshold": threshold,
        "retained_features": parameters,
        "excluded_features": excluded,
        "test_partition_used": False,
    }
    _write_json_atomic(parameter_payload, parameters_path)
    covered = sum(1 for item in event_evidence if item["covered"])
    report = {
        "status": "valid",
        "schema_version": contract["schema_version"],
        "contract": {"path": config_path.as_posix(), "sha256": _sha256(config_path)},
        "inputs": inputs,
        "fit": {
            "eligible_training_reference_rows": reference_rows,
            "retained_feature_count": len(parameters),
            "excluded_zero_iqr_feature_count": len(excluded),
            "parameters_path": parameters_path.as_posix(),
            "parameters_sha256": _sha256(parameters_path),
            "threshold": threshold,
            "threshold_quantile": contract["score"]["threshold_quantile"],
        },
        "validation": {
            "scored_rows": validation_rows,
            "scores_path": scores_path.as_posix(),
            "scores_sha256": _sha256(scores_path),
            "training_score_summary": train_summary,
            "validation_score_summary": validation_summary,
            "documented_event_count": len(event_evidence),
            "documented_events_covered": covered,
            "documented_event_coverage_fraction": None if not event_evidence else covered / len(event_evidence),
            "documented_event_evidence": event_evidence,
            "unlabeled_alarm_burden_rows": int(burden_rows),
            "unlabeled_alarm_count": int(burden_alarms),
            "alarm_burden_fraction": None if not burden_rows else int(burden_alarms) / int(burden_rows),
            "alarms_per_24_observed_hours": None if not observed_hours else int(burden_alarms) * 24.0 / observed_hours,
        },
        "governance": {
            "parameters_fitted_on_training_reference_only": True,
            "threshold_fitted_on_training_reference_only": True,
            "parameters_frozen_for_validation": True,
            "test_partition_locked": True,
            "test_rows_scored": 0,
            "unverified_rows_are_verified_healthy": False,
            "alarm_burden_is_false_positive_rate": False,
            "unsupported_classification_metrics_reported": False,
        },
        "software": {"python_version": platform.python_version(), "duckdb_version": duckdb.__version__},
    }
    _write_json_atomic(report, report_path)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fit and validate the MetroPT-3 robust-distance baseline.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    arguments = build_argument_parser().parse_args()
    try:
        report = run_robust_distance(arguments.config, overwrite=arguments.overwrite)
    except (RobustDistanceError, duckdb.Error, OSError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps({
        "processing_status": "robust_distance_validation_completed",
        "eligible_training_reference_rows": report["fit"]["eligible_training_reference_rows"],
        "validation_scored_rows": report["validation"]["scored_rows"],
        "test_rows_scored": report["governance"]["test_rows_scored"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

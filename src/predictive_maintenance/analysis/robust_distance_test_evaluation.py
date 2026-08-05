"""Evaluate the completely frozen MetroPT-3 robust-distance baseline on test data.

The workflow loads the training-derived parameters and the validation-stage
threshold decision without refitting. It scores only eligible test rows,
reports supported operational evidence, and preserves uncertainty for
unverified rows.
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
DEFAULT_CONFIG_PATH = (
    PROJECT_ROOT / "config" / "metropt3_robust_distance_test_evaluation.json"
)


class RobustDistanceTestEvaluationError(ValueError):
    """Raised when frozen-baseline test evaluation would violate governance."""


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
        raise RobustDistanceTestEvaluationError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RobustDistanceTestEvaluationError(
            f"Invalid {label} JSON: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise RobustDistanceTestEvaluationError(
            f"{label} must contain a JSON object."
        )
    return payload


def _resolve(value: str) -> Path:
    return PROJECT_ROOT / value


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate_contract(contract: dict[str, Any]) -> None:
    """Reject refitting, threshold revision, label fabrication, and scope drift."""
    for section in ("inputs", "evaluation", "governance", "outputs"):
        if not isinstance(contract.get(section), dict):
            raise RobustDistanceTestEvaluationError(
                f"Contract section must be an object: {section}"
            )

    evaluation = contract["evaluation"]
    governance = contract["governance"]
    outputs = contract["outputs"]

    if evaluation.get("partition") != "test":
        raise RobustDistanceTestEvaluationError(
            "The governed evaluation partition must be test."
        )
    required_columns = {
        "scoring_eligibility_column": "eligible_for_scoring",
        "known_event_eligibility_column": "eligible_for_known_event_evaluation",
        "alarm_burden_eligibility_column": "eligible_for_alarm_burden",
    }
    for field, expected in required_columns.items():
        if evaluation.get(field) != expected:
            raise RobustDistanceTestEvaluationError(
                f"evaluation.{field} must be {expected}."
            )

    quantile = evaluation.get("selected_threshold_quantile")
    if (
        isinstance(quantile, bool)
        or not isinstance(quantile, (int, float))
        or not 0 < float(quantile) < 1
    ):
        raise RobustDistanceTestEvaluationError(
            "The selected threshold quantile must be between zero and one."
        )
    sampling = evaluation.get("expected_sampling_seconds")
    if (
        isinstance(sampling, bool)
        or not isinstance(sampling, (int, float))
        or not math.isfinite(float(sampling))
        or float(sampling) <= 0
    ):
        raise RobustDistanceTestEvaluationError(
            "Expected sampling seconds must be a positive finite number."
        )

    required_true = (
        "parameters_must_be_frozen",
        "threshold_must_match_validation_decision",
        "validation_must_precede_test",
        "one_time_test_evaluation",
        "no_refit_or_threshold_revision",
    )
    if any(governance.get(name) is not True for name in required_true):
        raise RobustDistanceTestEvaluationError(
            "Frozen parameters, frozen threshold, completed validation, one-time "
            "test evaluation, and no-refit controls are required."
        )
    if governance.get("unverified_rows_are_verified_healthy") is not False:
        raise RobustDistanceTestEvaluationError(
            "Unverified rows cannot be represented as verified healthy."
        )
    if governance.get("alarm_burden_is_false_positive_rate") is not False:
        raise RobustDistanceTestEvaluationError(
            "Alarm burden cannot be represented as false-positive rate."
        )
    if governance.get("advanced_model_comparison_enabled") is not False:
        raise RobustDistanceTestEvaluationError(
            "Advanced-model comparison must remain disabled during this evaluation."
        )
    if outputs.get("compression") not in {"ZSTD", "SNAPPY", "GZIP"}:
        raise RobustDistanceTestEvaluationError(
            "Parquet compression must be ZSTD, SNAPPY, or GZIP."
        )


def _validate_retained_features(
    retained: Any,
) -> list[dict[str, Any]]:
    if not isinstance(retained, list) or not retained:
        raise RobustDistanceTestEvaluationError(
            "Frozen parameters require at least one retained feature."
        )
    names: list[str] = []
    validated: list[dict[str, Any]] = []
    for item in retained:
        if not isinstance(item, dict):
            raise RobustDistanceTestEvaluationError(
                "Every retained feature entry must be an object."
            )
        feature = item.get("feature")
        median = item.get("median")
        iqr = item.get("iqr")
        if not isinstance(feature, str) or not feature:
            raise RobustDistanceTestEvaluationError(
                "Every retained feature requires a non-empty name."
            )
        if feature in names:
            raise RobustDistanceTestEvaluationError(
                f"Duplicate retained feature: {feature}"
            )
        if (
            isinstance(median, bool)
            or not isinstance(median, (int, float))
            or not math.isfinite(float(median))
        ):
            raise RobustDistanceTestEvaluationError(
                f"Frozen median must be finite: {feature}"
            )
        if (
            isinstance(iqr, bool)
            or not isinstance(iqr, (int, float))
            or not math.isfinite(float(iqr))
            or float(iqr) <= 0
        ):
            raise RobustDistanceTestEvaluationError(
                f"Frozen IQR must be positive and finite: {feature}"
            )
        names.append(feature)
        validated.append(
            {"feature": feature, "median": float(median), "iqr": float(iqr)}
        )
    return validated


def _validate_frozen_inputs(
    parameters: dict[str, Any],
    validation_report: dict[str, Any],
    diagnostic_report: dict[str, Any],
    expected_quantile: float,
) -> tuple[list[dict[str, Any]], float]:
    """Verify one unchanged parameter and decision chain before test access."""
    if (
        parameters.get("status") != "frozen_before_validation"
        or parameters.get("test_partition_used") is not False
    ):
        raise RobustDistanceTestEvaluationError(
            "Parameters must be frozen before validation with no prior test use."
        )
    if (
        validation_report.get("status") != "valid"
        or validation_report.get("governance", {}).get("test_rows_scored") != 0
        or validation_report.get("governance", {}).get("test_partition_locked")
        is not True
    ):
        raise RobustDistanceTestEvaluationError(
            "Validation evidence must be valid and must show a locked, unused test partition."
        )
    decision = diagnostic_report.get("decision", {})
    if (
        diagnostic_report.get("status") != "valid"
        or decision.get("decision_status") != "frozen_after_validation_diagnosis"
        or decision.get("test_partition_remains_locked") is not True
    ):
        raise RobustDistanceTestEvaluationError(
            "Diagnostic evidence must contain a frozen validation decision and locked test partition."
        )

    parameter_quantile = parameters.get("threshold_quantile")
    validation_quantile = validation_report.get("fit", {}).get("threshold_quantile")
    diagnosis_quantile = decision.get("selected_threshold_quantile")
    quantiles = (
        float(expected_quantile),
        parameter_quantile,
        validation_quantile,
        diagnosis_quantile,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in quantiles
    ) or len({float(value) for value in quantiles}) != 1:
        raise RobustDistanceTestEvaluationError(
            "The selected threshold quantile does not match across frozen evidence."
        )

    parameter_threshold = parameters.get("threshold")
    validation_threshold = validation_report.get("fit", {}).get("threshold")
    diagnosis_threshold = diagnostic_report.get("frozen_baseline", {}).get(
        "threshold"
    )
    thresholds = (parameter_threshold, validation_threshold, diagnosis_threshold)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in thresholds
    ):
        raise RobustDistanceTestEvaluationError(
            "Frozen threshold evidence is missing or non-finite."
        )
    if len({float(value) for value in thresholds}) != 1:
        raise RobustDistanceTestEvaluationError(
            "The frozen threshold does not match across validation evidence."
        )

    retained = _validate_retained_features(parameters.get("retained_features"))
    expected_count = diagnostic_report.get("frozen_baseline", {}).get(
        "retained_feature_count"
    )
    if expected_count != len(retained):
        raise RobustDistanceTestEvaluationError(
            "Retained feature count does not match the frozen diagnostic evidence."
        )
    return retained, float(parameter_threshold)


def _score_expression(parameters: list[dict[str, Any]]) -> str:
    retained = _validate_retained_features(parameters)
    terms = [
        f"abs(({_quote_identifier(item['feature'])} - {item['median']!r}) / "
        f"{item['iqr']!r})"
        for item in retained
    ]
    return "greatest(" + ", ".join(terms) + ")"


def _score_summary(
    connection: duckdb.DuckDBPyConnection,
) -> dict[str, float | int | None]:
    row = connection.execute(
        """
        SELECT
            count(*),
            min(robust_distance_score),
            quantile_cont(robust_distance_score, 0.5),
            quantile_cont(robust_distance_score, 0.95),
            quantile_cont(robust_distance_score, 0.995),
            max(robust_distance_score)
        FROM test_scores
        """
    ).fetchone()
    names = ("row_count", "minimum", "median", "p95", "p995", "maximum")
    return {
        name: (
            int(value)
            if name == "row_count"
            else (None if value is None else float(value))
        )
        for name, value in zip(names, row)
    }


def _validate_upstream_files(
    connection: duckdb.DuckDBPyConnection,
    paths: dict[str, Path],
) -> dict[str, Any]:
    for name, path in paths.items():
        if not path.is_file():
            raise RobustDistanceTestEvaluationError(
                f"Input does not exist ({name}): {path}"
            )

    feature_report = _read_json(paths["feature_report"], "Feature evidence")
    eligibility_report = _read_json(
        paths["eligibility_report"], "Eligibility evidence"
    )
    if (
        feature_report.get("status") != "valid"
        or eligibility_report.get("status") != "valid"
    ):
        raise RobustDistanceTestEvaluationError(
            "Feature and eligibility evidence must both be valid."
        )

    feature_sha = _sha256(paths["feature_parquet"])
    eligibility_sha = _sha256(paths["eligibility_parquet"])
    if feature_report.get("output", {}).get("parquet_sha256") != feature_sha:
        raise RobustDistanceTestEvaluationError(
            "Feature Parquet SHA-256 does not match its evidence report."
        )
    if eligibility_report.get("output", {}).get("parquet_sha256") != eligibility_sha:
        raise RobustDistanceTestEvaluationError(
            "Eligibility Parquet SHA-256 does not match its evidence report."
        )

    feature_source = f"read_parquet({_quote_literal(paths['feature_parquet'])})"
    eligibility_source = (
        f"read_parquet({_quote_literal(paths['eligibility_parquet'])})"
    )
    feature_count = int(
        connection.execute(f"SELECT count(*) FROM {feature_source}").fetchone()[0]
    )
    eligibility_count = int(
        connection.execute(f"SELECT count(*) FROM {eligibility_source}").fetchone()[0]
    )
    if feature_count == 0 or feature_count != eligibility_count:
        raise RobustDistanceTestEvaluationError(
            "Feature and eligibility inputs must contain the same non-empty row count."
        )
    mismatch = int(
        connection.execute(
            f"""
            SELECT count(*)
            FROM {feature_source} f
            FULL OUTER JOIN {eligibility_source} e USING (timestamp)
            WHERE f.timestamp IS NULL OR e.timestamp IS NULL
            """
        ).fetchone()[0]
    )
    if mismatch:
        raise RobustDistanceTestEvaluationError(
            "Feature and eligibility timestamps do not match."
        )
    partition_mismatch = int(
        connection.execute(
            f"""
            SELECT count(*)
            FROM {feature_source} f
            JOIN {eligibility_source} e USING (timestamp)
            WHERE f.partition IS DISTINCT FROM e.partition
            """
        ).fetchone()[0]
    )
    if partition_mismatch:
        raise RobustDistanceTestEvaluationError(
            "Feature and eligibility partition assignments do not match."
        )
    return {
        "row_count": feature_count,
        "feature_parquet_sha256": feature_sha,
        "eligibility_parquet_sha256": eligibility_sha,
    }


def run_test_evaluation(
    config_path: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Score eligible test rows once using the completely frozen baseline."""
    contract = _read_json(config_path, "Test-evaluation contract")
    validate_contract(contract)
    paths = {name: _resolve(value) for name, value in contract["inputs"].items()}
    scores_path = _resolve(contract["outputs"]["test_scores"])
    report_path = _resolve(contract["outputs"]["report"])
    for path in (scores_path, report_path):
        if path.exists() and not overwrite:
            raise RobustDistanceTestEvaluationError(
                f"Output already exists; use --overwrite only for a controlled "
                f"deterministic rerun: {path}"
            )

    connection = duckdb.connect(database=":memory:")
    temporary_scores = scores_path.with_name(scores_path.name + ".part")
    try:
        input_evidence = _validate_upstream_files(connection, paths)
        parameters = _read_json(paths["frozen_parameters"], "Frozen parameters")
        validation_report = _read_json(
            paths["validation_report"], "Validation report"
        )
        diagnostic_report = _read_json(
            paths["diagnostic_report"], "Diagnostic report"
        )
        retained, threshold = _validate_frozen_inputs(
            parameters,
            validation_report,
            diagnostic_report,
            float(contract["evaluation"]["selected_threshold_quantile"]),
        )

        if (
            validation_report.get("fit", {}).get("parameters_sha256")
            != _sha256(paths["frozen_parameters"])
        ):
            raise RobustDistanceTestEvaluationError(
                "Frozen parameter file SHA-256 does not match validation evidence."
            )

        feature_source = f"read_parquet({_quote_literal(paths['feature_parquet'])})"
        eligibility_source = (
            f"read_parquet({_quote_literal(paths['eligibility_parquet'])})"
        )
        columns = {
            str(row[0])
            for row in connection.execute(
                f"DESCRIBE SELECT * FROM {feature_source}"
            ).fetchall()
        }
        missing_features = [
            item["feature"] for item in retained if item["feature"] not in columns
        ]
        if missing_features:
            raise RobustDistanceTestEvaluationError(
                f"Feature Parquet is missing frozen features: {missing_features}"
            )

        expression = _score_expression(retained)
        connection.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW joined_test AS
            SELECT
                f.*,
                e.eligible_for_scoring,
                e.eligible_for_known_event_evaluation,
                e.eligible_for_alarm_burden
            FROM {feature_source} f
            JOIN {eligibility_source} e USING (timestamp)
            WHERE f.partition = 'test'
              AND e.partition = 'test'
              AND e.eligible_for_scoring
            """
        )
        scored_rows = int(
            connection.execute("SELECT count(*) FROM joined_test").fetchone()[0]
        )
        if scored_rows == 0:
            raise RobustDistanceTestEvaluationError(
                "The eligible test scoring population is empty."
            )
        null_conditions = " OR ".join(
            f"{_quote_identifier(item['feature'])} IS NULL" for item in retained
        )
        null_rows = int(
            connection.execute(
                f"SELECT count(*) FROM joined_test WHERE {null_conditions}"
            ).fetchone()[0]
        )
        if null_rows:
            raise RobustDistanceTestEvaluationError(
                "Eligible test rows contain null values in frozen retained features."
            )

        connection.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW test_scores AS
            SELECT
                timestamp,
                segment_id,
                partition,
                target_state,
                source_event,
                eligible_for_known_event_evaluation,
                eligible_for_alarm_burden,
                {expression} AS robust_distance_score,
                {expression} > {threshold!r} AS alarm
            FROM joined_test
            ORDER BY timestamp
            """
        )
        non_test_rows = int(
            connection.execute(
                "SELECT count(*) FROM test_scores WHERE partition != 'test'"
            ).fetchone()[0]
        )
        if non_test_rows:
            raise RobustDistanceTestEvaluationError(
                "A non-test row entered the test scoring output."
            )

        event_rows = connection.execute(
            """
            SELECT
                source_event,
                min(timestamp),
                min(timestamp) FILTER (WHERE alarm),
                count(*),
                count(*) FILTER (WHERE alarm)
            FROM test_scores
            WHERE eligible_for_known_event_evaluation
            GROUP BY source_event
            ORDER BY min(timestamp)
            """
        ).fetchall()
        event_evidence = [
            {
                "source_event": str(event),
                "event_scored_rows": int(rows),
                "covered": first_alarm is not None,
                "first_alarm_latency_seconds": (
                    None
                    if first_alarm is None
                    else (first_alarm - start).total_seconds()
                ),
                "alarm_rows_within_documented_event": int(alarm_rows),
            }
            for event, start, first_alarm, rows, alarm_rows in event_rows
        ]
        burden_rows, burden_alarms = connection.execute(
            """
            SELECT count(*), count(*) FILTER (WHERE alarm)
            FROM test_scores
            WHERE eligible_for_alarm_burden
            """
        ).fetchone()
        sampling = float(contract["evaluation"]["expected_sampling_seconds"])
        observed_hours = int(burden_rows) * sampling / 3600.0
        score_summary = _score_summary(connection)

        temporary_scores.parent.mkdir(parents=True, exist_ok=True)
        temporary_scores.unlink(missing_ok=True)
        connection.execute(
            f"COPY test_scores TO {_quote_literal(temporary_scores)} "
            f"(FORMAT PARQUET, COMPRESSION "
            f"{_quote_literal(contract['outputs']['compression'])})"
        )
        temporary_scores.replace(scores_path)
    except Exception:
        temporary_scores.unlink(missing_ok=True)
        raise
    finally:
        connection.close()

    covered = sum(1 for item in event_evidence if item["covered"])
    report = {
        "status": "valid",
        "schema_version": contract["schema_version"],
        "contract": {
            "path": config_path.as_posix(),
            "sha256": _sha256(config_path),
        },
        "inputs": {
            **input_evidence,
            "frozen_parameters_sha256": _sha256(paths["frozen_parameters"]),
            "validation_report_sha256": _sha256(paths["validation_report"]),
            "diagnostic_report_sha256": _sha256(paths["diagnostic_report"]),
        },
        "frozen_baseline": {
            "family": "maximum_absolute_robust_z_score",
            "retained_feature_count": len(retained),
            "threshold_quantile": float(
                contract["evaluation"]["selected_threshold_quantile"]
            ),
            "threshold": threshold,
            "parameters_loaded_without_refit": True,
            "threshold_loaded_without_revision": True,
        },
        "test": {
            "scored_rows": scored_rows,
            "scores_path": scores_path.as_posix(),
            "scores_sha256": _sha256(scores_path),
            "score_summary": score_summary,
            "documented_event_count": len(event_evidence),
            "documented_events_covered": covered,
            "documented_event_coverage_fraction": (
                None if not event_evidence else covered / len(event_evidence)
            ),
            "documented_event_evidence": event_evidence,
            "unlabeled_alarm_burden_rows": int(burden_rows),
            "unlabeled_alarm_count": int(burden_alarms),
            "alarm_burden_fraction": (
                None
                if not burden_rows
                else int(burden_alarms) / int(burden_rows)
            ),
            "alarms_per_24_observed_hours": (
                None
                if not observed_hours
                else int(burden_alarms) * 24.0 / observed_hours
            ),
        },
        "governance": {
            "training_rows_scored": 0,
            "validation_rows_scored": 0,
            "only_eligible_test_rows_scored": True,
            "parameters_fitted_during_test_evaluation": False,
            "threshold_revised_using_test_evidence": False,
            "unverified_rows_are_verified_healthy": False,
            "alarm_burden_is_false_positive_rate": False,
            "unsupported_classification_metrics_reported": False,
            "advanced_model_comparison_started": False,
            "one_time_test_evaluation_complete": True,
        },
        "limitations": [
            "Unverified operational rows are not verified healthy negatives.",
            "Alarm burden is not a false-positive rate.",
            "Documented-event coverage is based only on the governed events present in the locked test partition.",
            "The robust-distance score does not estimate failure probability.",
            "Test evidence must not be used to revise this frozen baseline before an advanced-model comparison is specified separately.",
        ],
        "software": {
            "python_version": platform.python_version(),
            "duckdb_version": duckdb.__version__,
        },
    }
    _write_json_atomic(report, report_path)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the completely frozen MetroPT-3 robust-distance baseline "
            "on eligible test rows."
        )
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    arguments = build_argument_parser().parse_args()
    try:
        report = run_test_evaluation(
            arguments.config,
            overwrite=arguments.overwrite,
        )
    except (RobustDistanceTestEvaluationError, duckdb.Error, OSError) as error:
        print(f"ERROR: {error}")
        return 1
    print(
        json.dumps(
            {
                "processing_status": "robust_distance_test_evaluation_completed",
                "test_scored_rows": report["test"]["scored_rows"],
                "documented_event_count": report["test"][
                    "documented_event_count"
                ],
                "documented_events_covered": report["test"][
                    "documented_events_covered"
                ],
                "unlabeled_alarm_count": report["test"][
                    "unlabeled_alarm_count"
                ],
                "training_rows_scored": report["governance"][
                    "training_rows_scored"
                ],
                "validation_rows_scored": report["governance"][
                    "validation_rows_scored"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

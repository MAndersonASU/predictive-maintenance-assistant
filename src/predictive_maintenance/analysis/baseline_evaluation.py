"""Validate the governed MetroPT-3 baseline-evaluation contract.

The workflow materializes eligibility evidence for a future transparent
baseline. It does not fit preprocessing, train a model, generate anomaly
scores or alarms, or report performance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "metropt3_baseline_evaluation.json"
DEFAULT_FEATURE_PATH = PROJECT_ROOT / "data" / "processed" / "metropt3_features.parquet"
DEFAULT_FEATURE_REPORT_PATH = PROJECT_ROOT / "outputs" / "metropt3_feature_engineering_report.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "metropt3_baseline_eligibility.parquet"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "metropt3_baseline_evaluation_contract_report.json"
REQUIRED_COLUMNS = (
    "timestamp",
    "segment_id",
    "partition",
    "target_state",
    "binary_target",
    "source_event",
    "exclusion_reason",
    "has_full_30_row_history",
)
PARTITIONS = ("train", "validation", "test")


class BaselineEvaluationError(ValueError):
    """Raised when the baseline-evaluation contract is unsafe or inconsistent."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _quote_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise BaselineEvaluationError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BaselineEvaluationError(f"Invalid {label} JSON: {error}") from error
    if not isinstance(payload, dict):
        raise BaselineEvaluationError(f"{label} must contain a JSON object.")
    return payload


def load_contract(path: Path) -> dict[str, Any]:
    """Load and validate the governed baseline-evaluation contract."""
    payload = _read_json(path, "Baseline-evaluation contract")
    validate_contract(payload)
    return payload


def validate_contract(payload: dict[str, Any]) -> None:
    """Reject label fabrication, temporal leakage, and premature evaluation."""
    if not isinstance(payload, dict):
        raise BaselineEvaluationError("Contract must be a JSON object.")
    sections = ("dataset", "population", "baseline", "evaluation", "governance", "outputs")
    if not all(isinstance(payload.get(name), dict) for name in sections):
        raise BaselineEvaluationError(f"Contract sections must be objects: {sections}")

    population = payload["population"]
    baseline = payload["baseline"]
    evaluation = payload["evaluation"]
    governance = payload["governance"]

    if population.get("partition_order") != list(PARTITIONS):
        raise BaselineEvaluationError("partition_order must be train, validation, test.")
    if population.get("unverified_rows_are_negative") is not False:
        raise BaselineEvaluationError("Unverified rows must not be treated as negatives.")
    if population.get("reference_population_interpretation") != "unlabeled_operational_reference_not_verified_healthy":
        raise BaselineEvaluationError("The reference population must remain explicitly unlabeled.")
    if population.get("require_no_exclusion_reason") is not True:
        raise BaselineEvaluationError("Reference and scoring rows must have no exclusion reason.")
    if population.get("require_full_30_row_history") is not True:
        raise BaselineEvaluationError("Rows must have complete governed 30-row history.")

    if baseline.get("family") != "training_reference_robust_distance":
        raise BaselineEvaluationError("The governed baseline family must remain transparent.")
    preprocessing = baseline.get("preprocessing")
    threshold = baseline.get("alarm_threshold")
    if not isinstance(preprocessing, dict) or not isinstance(threshold, dict):
        raise BaselineEvaluationError("Preprocessing and alarm_threshold must be objects.")
    if preprocessing.get("fit_partition") != "train" or preprocessing.get("fit_state") != population.get("unlabeled_reference_state"):
        raise BaselineEvaluationError("Preprocessing fit scope must be eligible unlabeled training rows only.")
    if preprocessing.get("fit_on_eligible_reference_rows_only") is not True:
        raise BaselineEvaluationError("Preprocessing must fit only the eligible reference population.")
    if preprocessing.get("apply_frozen_parameters_to_later_partitions") is not True:
        raise BaselineEvaluationError("Training parameters must remain frozen for later partitions.")
    if threshold.get("fit_partition") != "train" or threshold.get("freeze_before_validation") is not True:
        raise BaselineEvaluationError("Alarm threshold calibration must be training-only and frozen.")
    quantile = threshold.get("quantile")
    if isinstance(quantile, bool) or not isinstance(quantile, (int, float)) or not 0 < quantile < 1:
        raise BaselineEvaluationError("Alarm threshold quantile must be between zero and one.")
    if threshold.get("test_partition_locked_until_method_is_frozen") is not True:
        raise BaselineEvaluationError("The test partition must remain locked until the method is frozen.")

    for control in ("chronological_only", "segment_safe", "validation_precedes_test"):
        if evaluation.get(control) is not True:
            raise BaselineEvaluationError(f"evaluation.{control} must be true.")
    unsupported = set(evaluation.get("unsupported_metrics", []))
    required_unsupported = {"accuracy", "precision", "specificity", "false_positive_rate", "roc_auc"}
    if not required_unsupported.issubset(unsupported):
        raise BaselineEvaluationError("Unsupported classification metrics must remain blocked.")
    if evaluation.get("alarm_burden_is_false_positive_rate") is not False:
        raise BaselineEvaluationError("Alarm burden must not be described as false-positive rate.")

    for control in (
        "learned_preprocessing_enabled_for_this_validation",
        "model_fitting_enabled_for_this_validation",
        "score_generation_enabled_for_this_validation",
        "alarm_generation_enabled_for_this_validation",
        "performance_reporting_enabled_for_this_validation",
    ):
        if governance.get(control) is not False:
            raise BaselineEvaluationError(f"governance.{control} must be false for this validation.")


def _validate_inputs(
    connection: duckdb.DuckDBPyConnection,
    contract: dict[str, Any],
    feature_path: Path,
    feature_report_path: Path,
    feature_contract_path: Path,
) -> dict[str, Any]:
    if not feature_path.is_file():
        raise BaselineEvaluationError(f"Feature Parquet does not exist: {feature_path}")
    feature_report = _read_json(feature_report_path, "Feature-engineering evidence")
    if feature_report.get("status") != "valid":
        raise BaselineEvaluationError("Feature-engineering evidence status must be valid.")
    if not feature_contract_path.is_file():
        raise BaselineEvaluationError(f"Feature contract does not exist: {feature_contract_path}")

    dataset = contract["dataset"]
    contract_checksum = _sha256(feature_contract_path)
    if contract_checksum != dataset.get("feature_contract_sha256"):
        raise BaselineEvaluationError("Feature-contract SHA-256 does not match the baseline contract.")
    feature_checksum = _sha256(feature_path)
    reported_checksum = feature_report.get("output", {}).get("parquet_sha256")
    if feature_checksum != reported_checksum:
        raise BaselineEvaluationError("Feature Parquet SHA-256 does not match its evidence report.")

    source = f"read_parquet({_quote_literal(feature_path)})"
    columns = [str(row[0]) for row in connection.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()]
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise BaselineEvaluationError(f"Feature Parquet is missing columns: {missing}")
    row_count = int(connection.execute(f"SELECT count(*) FROM {source}").fetchone()[0])
    if row_count == 0:
        raise BaselineEvaluationError("Feature Parquet contains no rows.")
    if feature_report.get("output", {}).get("row_count") != row_count:
        raise BaselineEvaluationError("Feature row count does not match its evidence report.")
    invalid_binary = int(connection.execute(
        f"""
        SELECT count(*) FROM {source}
        WHERE
            (target_state = 'documented_failure' AND binary_target IS DISTINCT FROM 1)
            OR (target_state != 'documented_failure' AND binary_target IS NOT NULL)
        """
    ).fetchone()[0])
    if invalid_binary:
        raise BaselineEvaluationError("Documented-positive binary targets are inconsistent.")
    return {
        "row_count": row_count,
        "feature_parquet_sha256": feature_checksum,
        "feature_contract_sha256": contract_checksum,
        "columns": columns,
    }


def _create_eligibility_view(
    connection: duckdb.DuckDBPyConnection,
    contract: dict[str, Any],
    feature_path: Path,
) -> None:
    population = contract["population"]
    positive = _quote_literal(population["documented_positive_state"])
    unlabeled = _quote_literal(population["unlabeled_reference_state"])
    excluded = ", ".join(_quote_literal(value) for value in population["excluded_states"])
    source = f"read_parquet({_quote_literal(feature_path)})"
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW baseline_eligibility AS
        WITH governed AS (
            SELECT
                timestamp,
                segment_id,
                partition,
                target_state,
                binary_target,
                source_event,
                exclusion_reason,
                has_full_30_row_history,
                partition IN ('train', 'validation', 'test')
                    AND target_state NOT IN ({excluded})
                    AND exclusion_reason IS NULL
                    AND has_full_30_row_history = true AS eligible_common
            FROM {source}
        )
        SELECT
            timestamp,
            segment_id,
            partition,
            target_state,
            binary_target,
            source_event,
            exclusion_reason,
            has_full_30_row_history,
            eligible_common AND partition = 'train' AND target_state = {unlabeled}
                AND binary_target IS NULL AS eligible_for_reference_fit,
            eligible_common AND target_state IN ({unlabeled}, {positive})
                AS eligible_for_scoring,
            eligible_common AND partition IN ('validation', 'test')
                AND target_state = {positive} AND binary_target = 1
                AS eligible_for_known_event_evaluation,
            eligible_common AND partition IN ('validation', 'test')
                AND target_state = {unlabeled} AND binary_target IS NULL
                AS eligible_for_alarm_burden,
            CASE
                WHEN NOT eligible_common THEN 'excluded'
                WHEN partition = 'train' AND target_state = {unlabeled} THEN 'unlabeled_reference'
                WHEN target_state = {positive} THEN 'documented_positive'
                WHEN target_state = {unlabeled} THEN 'unlabeled_scoring'
                ELSE 'excluded'
            END AS evaluation_role
        FROM governed
        ORDER BY timestamp
        """
    )


def _validate_temporal_order(connection: duckdb.DuckDBPyConnection) -> dict[str, dict[str, str]]:
    rows = connection.execute(
        """
        SELECT partition, min(timestamp), max(timestamp)
        FROM baseline_eligibility
        WHERE partition IN ('train', 'validation', 'test')
        GROUP BY partition
        """
    ).fetchall()
    coverage = {str(name): {"start": start.isoformat(), "end": end.isoformat()} for name, start, end in rows}
    if set(coverage) != set(PARTITIONS):
        raise BaselineEvaluationError("All three chronological partitions must contain rows.")
    if not (coverage["train"]["end"] < coverage["validation"]["start"] < coverage["validation"]["end"] < coverage["test"]["start"]):
        raise BaselineEvaluationError("Partition timestamps are not strictly chronological.")
    return coverage


def _write_parquet_atomic(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
    compression: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        connection.execute(
            f"COPY baseline_eligibility TO {_quote_literal(temporary)} "
            f"(FORMAT PARQUET, COMPRESSION {_quote_literal(compression)})"
        )
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    """Write formatted JSON with an atomic replacement and final newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate_baseline_evaluation(
    config_path: Path,
    feature_path: Path,
    feature_report_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    feature_contract_path: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate the contract and materialize governed row-eligibility evidence."""
    for path in (output_path, report_path):
        if path.exists() and not overwrite:
            raise BaselineEvaluationError(f"Output already exists; use --overwrite: {path}")
    contract = load_contract(config_path)
    if feature_contract_path is None:
        feature_contract_path = PROJECT_ROOT / contract["dataset"]["feature_contract_path"]

    connection = duckdb.connect(database=":memory:")
    try:
        input_evidence = _validate_inputs(
            connection, contract, feature_path, feature_report_path, feature_contract_path
        )
        _create_eligibility_view(connection, contract, feature_path)
        coverage = _validate_temporal_order(connection)
        count_rows = connection.execute(
            """
            SELECT
                count(*),
                count(*) FILTER (WHERE eligible_for_reference_fit),
                count(*) FILTER (WHERE eligible_for_scoring),
                count(*) FILTER (WHERE eligible_for_known_event_evaluation),
                count(*) FILTER (WHERE eligible_for_alarm_burden)
            FROM baseline_eligibility
            """
        ).fetchone()
        role_rows = connection.execute(
            "SELECT evaluation_role, count(*) FROM baseline_eligibility GROUP BY evaluation_role ORDER BY evaluation_role"
        ).fetchall()
        partition_rows = connection.execute(
            "SELECT coalesce(partition, 'excluded'), count(*) FROM baseline_eligibility GROUP BY partition ORDER BY coalesce(partition, 'excluded')"
        ).fetchall()
        if int(count_rows[0]) != input_evidence["row_count"]:
            raise BaselineEvaluationError("Eligibility output does not preserve input rows.")
        if int(count_rows[1]) == 0 or int(count_rows[2]) == 0:
            raise BaselineEvaluationError("Reference-fit and scoring populations must be non-empty.")
        _write_parquet_atomic(connection, output_path, contract["outputs"]["compression"])
    finally:
        connection.close()

    report = {
        "status": "valid",
        "schema_version": contract["schema_version"],
        "contract": {"path": config_path.as_posix(), "sha256": _sha256(config_path)},
        "input": input_evidence,
        "output": {
            "path": output_path.as_posix(),
            "row_count": int(count_rows[0]),
            "parquet_sha256": _sha256(output_path),
        },
        "evidence": {
            "partition_coverage": coverage,
            "partition_counts": {str(name): int(count) for name, count in partition_rows},
            "evaluation_role_counts": {str(name): int(count) for name, count in role_rows},
            "eligible_reference_fit_rows": int(count_rows[1]),
            "eligible_scoring_rows": int(count_rows[2]),
            "eligible_known_event_evaluation_rows": int(count_rows[3]),
            "eligible_alarm_burden_rows": int(count_rows[4]),
            "chronological_only": True,
            "segment_safe_history_required": True,
            "unverified_rows_are_negative": False,
        },
        "scope": {
            "reference_population_is_verified_healthy": False,
            "learned_preprocessing_fitted": False,
            "model_fitted": False,
            "scores_generated": False,
            "alarms_generated": False,
            "performance_metrics_reported": False,
        },
        "software": {
            "python_version": platform.python_version(),
            "duckdb_version": duckdb.__version__,
        },
    }
    write_json_atomic(report, report_path)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the MetroPT-3 baseline-evaluation contract.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--feature-input", type=Path, default=DEFAULT_FEATURE_PATH)
    parser.add_argument("--feature-report", type=Path, default=DEFAULT_FEATURE_REPORT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    arguments = build_argument_parser().parse_args()
    try:
        report = validate_baseline_evaluation(
            arguments.config,
            arguments.feature_input,
            arguments.feature_report,
            arguments.output,
            arguments.report,
            overwrite=arguments.overwrite,
        )
    except (BaselineEvaluationError, duckdb.Error, OSError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps({
        "processing_status": "baseline_evaluation_contract_validated",
        "row_count": report["output"]["row_count"],
        "output": report["output"]["path"],
        "report": arguments.report.as_posix(),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

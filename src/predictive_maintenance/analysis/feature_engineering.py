"""Build governed, causal, gap-aware MetroPT-3 features.

The workflow joins the verified sensor and target-state Parquet files by
timestamp, resets history whenever the observation segment or chronological
partition changes, and writes auditable feature evidence. It does not infer a
negative class, fit learned preprocessing, train a model, or report performance.
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
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "metropt3_feature_engineering.json"
DEFAULT_SENSOR_PATH = PROJECT_ROOT / "data" / "processed" / "metropt3_air_compressor.parquet"
DEFAULT_TARGET_PATH = PROJECT_ROOT / "data" / "processed" / "metropt3_target_states.parquet"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "metropt3_features.parquet"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "metropt3_feature_engineering_report.json"
GOVERNANCE_COLUMNS = (
    "timestamp", "segment_id", "partition", "target_state", "binary_target",
    "source_event", "exclusion_reason",
)


class FeatureEngineeringError(ValueError):
    """Raised when governed features cannot be created safely."""


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


def load_contract(path: Path) -> dict[str, Any]:
    """Load and validate the feature contract."""
    if not path.is_file():
        raise FeatureEngineeringError(f"Feature contract does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise FeatureEngineeringError(f"Invalid feature-contract JSON: {error}") from error
    validate_contract(payload)
    return payload


def validate_contract(payload: dict[str, Any]) -> None:
    """Reject any contract that weakens the governed leakage controls."""
    if not isinstance(payload, dict):
        raise FeatureEngineeringError("Feature contract must be a JSON object.")
    dataset = payload.get("dataset")
    contract = payload.get("feature_contract")
    governance = payload.get("governance")
    outputs = payload.get("outputs")
    if not all(isinstance(item, dict) for item in (dataset, contract, governance, outputs)):
        raise FeatureEngineeringError("dataset, feature_contract, governance, and outputs must be objects.")
    if contract.get("causal_direction") != "current_and_past_only":
        raise FeatureEngineeringError("causal_direction must be current_and_past_only.")
    for control in (
        "history_reset_on_segment_change",
        "history_reset_on_partition_change",
        "rolling_windows_include_current_row",
    ):
        if contract.get(control) is not True:
            raise FeatureEngineeringError(f"feature_contract.{control} must be true.")
    if governance.get("unverified_rows_are_negative") is not False:
        raise FeatureEngineeringError("governance.unverified_rows_are_negative must be false.")
    if governance.get("model_training_enabled") is not False:
        raise FeatureEngineeringError("governance.model_training_enabled must be false.")
    if governance.get("performance_reporting_enabled") is not False:
        raise FeatureEngineeringError("governance.performance_reporting_enabled must be false.")
    if governance.get("learned_preprocessing_enabled") is not False:
        raise FeatureEngineeringError("Learned preprocessing is disabled for this bounded lab.")
    if governance.get("learned_preprocessing_fit_scope") != "eligible_training_rows_only_if_enabled":
        raise FeatureEngineeringError("Learned preprocessing fit scope must remain training-only.")
    continuous = contract.get("continuous_signals")
    states = contract.get("operating_state_signals")
    if not continuous or not states or not all(isinstance(x, str) and x for x in continuous + states):
        raise FeatureEngineeringError("Signal lists must contain non-empty names.")
    if len(set(continuous + states)) != len(continuous + states):
        raise FeatureEngineeringError("Signal names must be unique.")
    if contract.get("lag_rows") != [1] or contract.get("difference_lag_rows") != 1:
        raise FeatureEngineeringError("This contract requires one-row lag and difference features.")
    windows = contract.get("rolling_windows_rows")
    if windows != [6, 30]:
        raise FeatureEngineeringError("This contract requires 6-row and 30-row rolling windows.")
    if contract.get("rolling_statistics") != ["mean", "stddev_population"]:
        raise FeatureEngineeringError("Only governed mean and population-standard-deviation windows are allowed.")
    for key in ("sensor_parquet_sha256", "target_states_parquet_sha256"):
        value = dataset.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise FeatureEngineeringError(f"dataset.{key} must be a SHA-256 value.")


def _columns(connection: duckdb.DuckDBPyConnection, path: Path) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet({_quote_literal(path)})"
        ).fetchall()
    ]


def _validate_inputs(
    connection: duckdb.DuckDBPyConnection,
    contract: dict[str, Any],
    sensor_path: Path,
    target_path: Path,
) -> dict[str, Any]:
    for label, path in (("Sensor", sensor_path), ("Target-state", target_path)):
        if not path.is_file():
            raise FeatureEngineeringError(f"{label} Parquet does not exist: {path}")
    dataset = contract["dataset"]
    checksums = {
        "sensor_parquet_sha256": _sha256(sensor_path),
        "target_states_parquet_sha256": _sha256(target_path),
    }
    for key, actual in checksums.items():
        if actual.lower() != dataset[key].lower():
            raise FeatureEngineeringError(
                f"{key} mismatch: expected {dataset[key]}, got {actual}."
            )
    sensor_columns = _columns(connection, sensor_path)
    target_columns = _columns(connection, target_path)
    required_sensor = [dataset["timestamp_column"]] + contract["feature_contract"]["continuous_signals"] + contract["feature_contract"]["operating_state_signals"]
    missing_sensor = [name for name in required_sensor if name not in sensor_columns]
    missing_target = [name for name in GOVERNANCE_COLUMNS if name not in target_columns]
    if missing_sensor:
        raise FeatureEngineeringError(f"Sensor input is missing columns: {missing_sensor}")
    if missing_target:
        raise FeatureEngineeringError(f"Target-state input is missing columns: {missing_target}")
    sensor = f"read_parquet({_quote_literal(sensor_path)})"
    targets = f"read_parquet({_quote_literal(target_path)})"
    sensor_count = int(connection.execute(f"SELECT count(*) FROM {sensor}").fetchone()[0])
    target_count = int(connection.execute(f"SELECT count(*) FROM {targets}").fetchone()[0])
    mismatch_count = int(connection.execute(
        f"""
        SELECT count(*) FROM (
          SELECT coalesce(s.timestamp, t.timestamp) AS timestamp
          FROM {sensor} s FULL OUTER JOIN {targets} t USING (timestamp)
          WHERE s.timestamp IS NULL OR t.timestamp IS NULL
        )
        """
    ).fetchone()[0])
    if sensor_count == 0 or sensor_count != target_count or mismatch_count:
        raise FeatureEngineeringError(
            "Sensor and target-state inputs must contain the same non-empty timestamp set."
        )
    return {"row_count": sensor_count, **checksums}


def _create_feature_view(
    connection: duckdb.DuckDBPyConnection,
    contract: dict[str, Any],
    sensor_path: Path,
    target_path: Path,
) -> list[str]:
    feature = contract["feature_contract"]
    continuous = feature["continuous_signals"]
    states = feature["operating_state_signals"]
    source_columns = continuous + states
    sensor_select = ",\n                ".join(f"s.{_quote_identifier(name)}" for name in source_columns)
    pass_through = ",\n                ".join(_quote_identifier(name) for name in source_columns)
    derived: list[str] = []
    derived_names: list[str] = []
    for name in continuous:
        quoted = _quote_identifier(name)
        specs = (
            (f"lag({quoted}, 1) OVER history_order", f"{name}__lag_1"),
            (f"{quoted} - lag({quoted}, 1) OVER history_order", f"{name}__delta_1"),
            (f"avg({quoted}) OVER history_6", f"{name}__mean_6"),
            (f"stddev_pop({quoted}) OVER history_6", f"{name}__stddev_pop_6"),
            (f"avg({quoted}) OVER history_30", f"{name}__mean_30"),
            (f"stddev_pop({quoted}) OVER history_30", f"{name}__stddev_pop_30"),
        )
        for expression, output_name in specs:
            derived.append(f"{expression} AS {_quote_identifier(output_name)}")
            derived_names.append(output_name)
    derived_sql = ",\n                ".join(derived)
    sensor = f"read_parquet({_quote_literal(sensor_path)})"
    targets = f"read_parquet({_quote_literal(target_path)})"
    governance = ",\n                ".join(f"t.{_quote_identifier(name)}" for name in GOVERNANCE_COLUMNS)
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW governed_features AS
        WITH joined AS (
            SELECT
                {governance},
                {sensor_select}
            FROM {targets} t
            INNER JOIN {sensor} s USING (timestamp)
        ),
        boundaries AS (
            SELECT *,
                CASE
                    WHEN lag(segment_id) OVER (ORDER BY timestamp) IS NULL THEN 1
                    WHEN segment_id IS DISTINCT FROM lag(segment_id) OVER (ORDER BY timestamp) THEN 1
                    WHEN partition IS DISTINCT FROM lag(partition) OVER (ORDER BY timestamp) THEN 1
                    ELSE 0
                END AS history_boundary
            FROM joined
        ),
        grouped AS (
            SELECT *,
                sum(history_boundary) OVER (ORDER BY timestamp ROWS UNBOUNDED PRECEDING) AS history_group_id
            FROM boundaries
        ),
        engineered AS (
            SELECT
                {', '.join(_quote_identifier(name) for name in GOVERNANCE_COLUMNS)},
                {pass_through},
                history_group_id,
                row_number() OVER history_order AS history_rows_available,
                {derived_sql}
            FROM grouped
            WINDOW
                history_order AS (PARTITION BY history_group_id ORDER BY timestamp),
                history_6 AS (PARTITION BY history_group_id ORDER BY timestamp ROWS BETWEEN 5 PRECEDING AND CURRENT ROW),
                history_30 AS (PARTITION BY history_group_id ORDER BY timestamp ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
        )
        SELECT
            *,
            history_rows_available >= 2 AS has_lag_1_history,
            history_rows_available >= 6 AS has_full_6_row_history,
            history_rows_available >= 30 AS has_full_30_row_history
        FROM engineered
        ORDER BY timestamp
        """
    )
    return list(GOVERNANCE_COLUMNS) + source_columns + [
        "history_group_id", "history_rows_available", *derived_names,
        "has_lag_1_history", "has_full_6_row_history", "has_full_30_row_history",
    ]


def _write_parquet_atomic(connection: duckdb.DuckDBPyConnection, output_path: Path, compression: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".part")
    if temporary.exists():
        temporary.unlink()
    try:
        connection.execute(
            f"COPY governed_features TO {_quote_literal(temporary)} (FORMAT PARQUET, COMPRESSION {_quote_literal(compression)})"
        )
        temporary.replace(output_path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    """Write formatted JSON with a final newline and atomic replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    if temporary.exists():
        temporary.unlink()
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def engineer_features(
    config_path: Path,
    sensor_path: Path,
    target_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the complete governed feature-engineering workflow."""
    for path in (output_path, report_path):
        if path.exists() and not overwrite:
            raise FeatureEngineeringError(f"Output already exists; use --overwrite: {path}")
    contract = load_contract(config_path)
    connection = duckdb.connect(database=":memory:")
    try:
        input_evidence = _validate_inputs(connection, contract, sensor_path, target_path)
        expected_columns = _create_feature_view(connection, contract, sensor_path, target_path)
        _write_parquet_atomic(connection, output_path, contract["outputs"]["compression"])
        output_count = int(connection.execute("SELECT count(*) FROM governed_features").fetchone()[0])
        segment_count, history_group_count = connection.execute(
            "SELECT count(DISTINCT segment_id), count(DISTINCT history_group_id) FROM governed_features"
        ).fetchone()
        null_lag_at_group_start = int(connection.execute(
            "SELECT count(*) FROM governed_features WHERE history_rows_available = 1 AND has_lag_1_history = false"
        ).fetchone()[0])
        invalid_lag = int(connection.execute(
            "SELECT count(*) FROM governed_features WHERE history_rows_available = 1 AND has_lag_1_history = true"
        ).fetchone()[0])
        state_rows = connection.execute(
            "SELECT target_state, count(*) FROM governed_features GROUP BY target_state ORDER BY target_state"
        ).fetchall()
        partition_rows = connection.execute(
            "SELECT coalesce(partition, 'excluded'), count(*) FROM governed_features GROUP BY partition ORDER BY coalesce(partition, 'excluded')"
        ).fetchall()
    finally:
        connection.close()
    if output_count != input_evidence["row_count"] or invalid_lag:
        output_path.unlink(missing_ok=True)
        raise FeatureEngineeringError("Post-write feature evidence failed governance checks.")
    report = {
        "status": "valid",
        "schema_version": contract["schema_version"],
        "contract": {"path": config_path.as_posix(), "sha256": _sha256(config_path)},
        "input": input_evidence,
        "output": {
            "path": output_path.as_posix(), "row_count": output_count,
            "column_count": len(expected_columns), "columns": expected_columns,
            "parquet_sha256": _sha256(output_path),
        },
        "evidence": {
            "rows_preserved": output_count == input_evidence["row_count"],
            "segment_count": int(segment_count),
            "history_group_count": int(history_group_count),
            "history_resets_with_null_lag": null_lag_at_group_start,
            "invalid_history_start_flags": invalid_lag,
            "target_state_counts": {str(k): int(v) for k, v in state_rows},
            "partition_counts": {str(k): int(v) for k, v in partition_rows},
            "causal_windows_only": True,
            "segment_and_partition_bounded": True,
        },
        "scope": {
            "unverified_rows_are_negative": False,
            "learned_preprocessing_fitted": False,
            "models_trained": False,
            "performance_metrics_reported": False,
        },
        "software": {"python_version": platform.python_version(), "duckdb_version": duckdb.__version__},
    }
    write_json_atomic(report, report_path)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build governed MetroPT-3 causal features.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--sensor-input", type=Path, default=DEFAULT_SENSOR_PATH)
    parser.add_argument("--target-input", type=Path, default=DEFAULT_TARGET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    arguments = build_argument_parser().parse_args()
    try:
        report = engineer_features(
            arguments.config, arguments.sensor_input, arguments.target_input,
            arguments.output, arguments.report, overwrite=arguments.overwrite,
        )
    except (FeatureEngineeringError, duckdb.Error, OSError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps({
        "processing_status": "feature_engineering_completed",
        "row_count": report["output"]["row_count"],
        "column_count": report["output"]["column_count"],
        "output": report["output"]["path"],
        "report": arguments.report.as_posix(),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

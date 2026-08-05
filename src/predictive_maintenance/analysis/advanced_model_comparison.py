"""Validate the governed MetroPT-3 advanced-model comparison contract.

This module verifies the evidence chain, candidate boundaries, deterministic
validation-selection rule, and test lock before any advanced model is fitted.
It does not read feature rows, fit preprocessing, train a model, generate
scores or alarms, select a candidate, or access the advanced-model test data.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "metropt3_advanced_model_comparison.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "metropt3_advanced_model_comparison_contract_report.json"
PARTITIONS = ("train", "validation", "test")
EXPECTED_COMMITTED_SOURCES = (
    "config/metropt3_baseline_evaluation.json",
    "config/metropt3_robust_distance.json",
    "config/metropt3_robust_distance_diagnosis.json",
    "config/metropt3_robust_distance_test_evaluation.json",
)
EXPECTED_GENERATED_SOURCES = (
    "outputs/metropt3_baseline_evaluation_contract_report.json",
    "outputs/metropt3_robust_distance_parameters.json",
    "outputs/metropt3_robust_distance_validation_report.json",
    "outputs/metropt3_robust_distance_diagnostic_report.json",
    "outputs/metropt3_robust_distance_test_report.json",
)
EXPECTED_SELECTION_CRITERIA = (
    ("documented_event_coverage", "maximize"),
    ("mean_first_alarm_latency_seconds_for_covered_events", "minimize"),
    ("alarms_per_24_observed_hours", "minimize"),
    ("candidate_complexity_rank", "minimize"),
)
EXPECTED_UNLOCK_CONDITIONS = (
    "comparison_contract_validated",
    "candidate_implementation_tested",
    "bounded_grid_evaluated_on_validation_only",
    "winning_candidate_and_threshold_frozen",
    "validation_decision_report_checksummed",
    "explicit_separate_test_authorization",
)


class AdvancedModelComparisonError(ValueError):
    """Raised when the comparison contract is unsafe or inconsistent."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise AdvancedModelComparisonError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise AdvancedModelComparisonError(f"Invalid {label} JSON: {error}") from error
    if not isinstance(payload, dict):
        raise AdvancedModelComparisonError(f"{label} must contain a JSON object.")
    return payload


def write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    """Write formatted JSON atomically with a final newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _require_object(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise AdvancedModelComparisonError(f"Contract section must be an object: {name}")
    return value


def _require_true(mapping: dict[str, Any], key: str, label: str) -> None:
    if mapping.get(key) is not True:
        raise AdvancedModelComparisonError(f"{label}.{key} must be true.")


def _require_false(mapping: dict[str, Any], key: str, label: str) -> None:
    if mapping.get(key) is not False:
        raise AdvancedModelComparisonError(f"{label}.{key} must be false.")


def _validate_baseline_reference(reference: dict[str, Any]) -> None:
    source_commit = reference.get("source_commit")
    if not isinstance(source_commit, str) or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise AdvancedModelComparisonError("baseline_reference.source_commit must be a 40-character lowercase Git SHA.")
    _require_true(reference, "finalized", "baseline_reference")
    if reference.get("family") != "maximum_absolute_robust_z_score":
        raise AdvancedModelComparisonError("The transparent robust-distance baseline family must remain finalized.")
    if reference.get("retained_feature_count") != 48:
        raise AdvancedModelComparisonError("The frozen baseline retained-feature count must remain 48.")
    if reference.get("selected_threshold_quantile") != 0.995:
        raise AdvancedModelComparisonError("The frozen baseline threshold quantile must remain 0.995.")
    if reference.get("frozen_threshold") != 7857.013759410036:
        raise AdvancedModelComparisonError("The frozen baseline threshold must not be revised.")
    if tuple(reference.get("committed_sources", [])) != EXPECTED_COMMITTED_SOURCES:
        raise AdvancedModelComparisonError("Committed baseline source references are incomplete or reordered.")
    if tuple(reference.get("generated_sources", [])) != EXPECTED_GENERATED_SOURCES:
        raise AdvancedModelComparisonError("Generated baseline evidence references are incomplete or reordered.")

    test_report = reference.get("test_report")
    if not isinstance(test_report, dict):
        raise AdvancedModelComparisonError("baseline_reference.test_report must be an object.")
    if test_report.get("path") != "outputs/metropt3_robust_distance_test_report.json":
        raise AdvancedModelComparisonError("The finalized baseline test-report path is incorrect.")
    checksum = test_report.get("sha256")
    if not isinstance(checksum, str) or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
        raise AdvancedModelComparisonError("The baseline test-report SHA-256 must be 64 lowercase hexadecimal characters.")
    if test_report.get("design_or_tuning_use") != "prohibited":
        raise AdvancedModelComparisonError("Baseline test evidence must be prohibited from design and tuning.")
    if test_report.get("future_comparison_use") != "reference_only_after_advanced_method_and_validation_decision_are_frozen":
        raise AdvancedModelComparisonError("Baseline test evidence may be used only after the advanced method is frozen.")


def _validate_population(population: dict[str, Any]) -> None:
    if population.get("partition_order") != list(PARTITIONS):
        raise AdvancedModelComparisonError("partition_order must be train, validation, test.")
    if population.get("development_partitions") != ["train", "validation"]:
        raise AdvancedModelComparisonError("Development must use train and validation only.")
    _require_false(population, "test_partition_access_enabled", "population")
    if population.get("fit_partition") != "train" or population.get("selection_partition") != "validation":
        raise AdvancedModelComparisonError("Fit must be training-only and selection must be validation-only.")
    expected_columns = {
        "fit_eligibility_column": "eligible_for_reference_fit",
        "scoring_eligibility_column": "eligible_for_scoring",
        "known_event_eligibility_column": "eligible_for_known_event_evaluation",
        "alarm_burden_eligibility_column": "eligible_for_alarm_burden",
    }
    for key, expected in expected_columns.items():
        if population.get(key) != expected:
            raise AdvancedModelComparisonError(f"population.{key} must remain {expected}.")
    if population.get("documented_positive_state") != "documented_failure":
        raise AdvancedModelComparisonError("The documented-positive state must remain documented_failure.")
    if population.get("unlabeled_state") != "unverified":
        raise AdvancedModelComparisonError("The unlabeled state must remain unverified.")
    _require_false(population, "unverified_rows_are_verified_healthy", "population")
    for key in ("require_no_exclusion_reason", "require_full_30_row_history", "chronological_only", "segment_safe", "partition_bounded"):
        _require_true(population, key, "population")


def _validate_candidate(candidate: dict[str, Any]) -> None:
    if candidate.get("family") != "isolation_forest":
        raise AdvancedModelComparisonError("The bounded candidate family must be isolation_forest.")
    if candidate.get("implementation") != "sklearn.ensemble.IsolationForest":
        raise AdvancedModelComparisonError("The candidate implementation must be sklearn.ensemble.IsolationForest.")
    if candidate.get("objective") != "unsupervised_anomaly_scoring":
        raise AdvancedModelComparisonError("The candidate objective must remain unsupervised anomaly scoring.")

    features = candidate.get("features")
    if not isinstance(features, dict):
        raise AdvancedModelComparisonError("candidate_model.features must be an object.")
    if features.get("source") != "frozen_robust_distance_retained_features" or features.get("count") != 48:
        raise AdvancedModelComparisonError("Every candidate must use the frozen 48-feature baseline set.")
    _require_true(features, "same_features_for_every_candidate", "candidate_model.features")
    _require_true(features, "test_data_feature_selection_prohibited", "candidate_model.features")

    preprocessing = candidate.get("preprocessing")
    if not isinstance(preprocessing, dict):
        raise AdvancedModelComparisonError("candidate_model.preprocessing must be an object.")
    if preprocessing.get("fit_scope") != "eligible_training_reference_rows_only":
        raise AdvancedModelComparisonError("Preprocessing fit scope must be eligible training-reference rows only.")
    if preprocessing.get("missing_or_nonfinite_policy") != "reject_before_fit":
        raise AdvancedModelComparisonError("Missing or non-finite candidate inputs must be rejected before fit.")
    if preprocessing.get("scaling") != "none":
        raise AdvancedModelComparisonError("Scaling must remain disabled for the bounded Isolation Forest comparison.")
    _require_true(preprocessing, "validation_fit_prohibited", "candidate_model.preprocessing")
    _require_true(preprocessing, "test_fit_prohibited", "candidate_model.preprocessing")

    fixed = candidate.get("fixed_parameters")
    if fixed != {"contamination": "auto", "bootstrap": False, "random_state": 42, "n_jobs": -1}:
        raise AdvancedModelComparisonError("Fixed Isolation Forest parameters do not match the governed contract.")

    grid = candidate.get("bounded_grid")
    expected_grid = {
        "n_estimators": [100, 200],
        "max_samples": [1024, 4096],
        "max_features": [0.5, 1.0],
    }
    if grid != expected_grid:
        raise AdvancedModelComparisonError("The Isolation Forest hyperparameter grid must remain bounded to eight candidates.")
    candidate_count = len(list(itertools.product(*expected_grid.values())))
    if candidate.get("candidate_count") != candidate_count:
        raise AdvancedModelComparisonError("candidate_count does not match the bounded hyperparameter grid.")

    score = candidate.get("score")
    if score != {"method": "negative_score_samples", "direction": "higher_is_more_unusual"}:
        raise AdvancedModelComparisonError("The governed candidate score definition is incorrect.")

    threshold = candidate.get("alarm_threshold")
    if not isinstance(threshold, dict):
        raise AdvancedModelComparisonError("candidate_model.alarm_threshold must be an object.")
    if threshold.get("method") != "eligible_training_score_quantile" or threshold.get("quantile") != 0.995:
        raise AdvancedModelComparisonError("The candidate threshold must be the fixed 0.995 training-score quantile.")
    if threshold.get("fit_partition") != "train":
        raise AdvancedModelComparisonError("The candidate threshold must be fitted on training scores only.")
    for key in ("freeze_before_validation", "validation_threshold_tuning_prohibited", "test_threshold_tuning_prohibited"):
        _require_true(threshold, key, "candidate_model.alarm_threshold")


def _validate_selection(selection: dict[str, Any]) -> None:
    if selection.get("partition") != "validation":
        raise AdvancedModelComparisonError("Candidate selection must use the validation partition only.")
    _require_false(selection, "test_evidence_available_to_selection", "validation_selection")
    if selection.get("rule") != "lexicographic":
        raise AdvancedModelComparisonError("The candidate-selection rule must be lexicographic.")
    criteria = selection.get("ordered_criteria")
    if not isinstance(criteria, list):
        raise AdvancedModelComparisonError("validation_selection.ordered_criteria must be a list.")
    actual = tuple((item.get("metric"), item.get("direction")) for item in criteria if isinstance(item, dict))
    if actual != EXPECTED_SELECTION_CRITERIA or len(criteria) != len(EXPECTED_SELECTION_CRITERIA):
        raise AdvancedModelComparisonError("The ordered candidate-selection criteria were changed.")
    if selection.get("complexity_tie_break_order") != ["n_estimators", "max_samples", "max_features"]:
        raise AdvancedModelComparisonError("The deterministic complexity tie-break order is incorrect.")
    supported = set(selection.get("supported_metrics", []))
    required_supported = {
        "documented_event_coverage",
        "first_alarm_latency_seconds",
        "alarm_contiguity_within_documented_event",
        "alarm_burden_fraction",
        "alarms_per_24_observed_hours",
        "score_distribution_drift",
    }
    if supported != required_supported:
        raise AdvancedModelComparisonError("Supported operational metrics are incomplete or expanded without governance.")
    unsupported = set(selection.get("unsupported_metrics", []))
    required_unsupported = {
        "accuracy",
        "precision",
        "recall_as_population_sensitivity",
        "specificity",
        "false_positive_rate",
        "roc_auc",
        "failure_probability",
    }
    if unsupported != required_unsupported:
        raise AdvancedModelComparisonError("Unsupported classification and probability claims must remain blocked.")
    _require_false(selection, "alarm_burden_is_false_positive_rate", "validation_selection")


def _validate_test_lock(test_lock: dict[str, Any]) -> None:
    _require_true(test_lock, "locked", "test_lock")
    _require_true(test_lock, "one_time_future_evaluation", "test_lock")
    _require_true(test_lock, "baseline_test_evidence_cannot_select_candidate", "test_lock")
    if tuple(test_lock.get("unlock_conditions", [])) != EXPECTED_UNLOCK_CONDITIONS:
        raise AdvancedModelComparisonError("The advanced-model test unlock conditions are incomplete or reordered.")


def _validate_governance(governance: dict[str, Any]) -> None:
    controls = (
        "model_fitting_enabled_for_this_validation",
        "learned_preprocessing_enabled_for_this_validation",
        "candidate_scoring_enabled_for_this_validation",
        "candidate_selection_enabled_for_this_validation",
        "advanced_test_evaluation_enabled_for_this_validation",
        "baseline_revision_enabled",
        "performance_claims_enabled_for_this_validation",
    )
    for control in controls:
        _require_false(governance, control, "governance")


def validate_contract(payload: dict[str, Any]) -> None:
    """Reject leakage, test reuse, label fabrication, and unbounded tuning."""
    if not isinstance(payload, dict):
        raise AdvancedModelComparisonError("Contract must be a JSON object.")
    if payload.get("schema_version") != 1:
        raise AdvancedModelComparisonError("schema_version must be 1.")
    reference = _require_object(payload, "baseline_reference")
    population = _require_object(payload, "population")
    candidate = _require_object(payload, "candidate_model")
    selection = _require_object(payload, "validation_selection")
    test_lock = _require_object(payload, "test_lock")
    governance = _require_object(payload, "governance")
    outputs = _require_object(payload, "outputs")

    _validate_baseline_reference(reference)
    _validate_population(population)
    _validate_candidate(candidate)
    _validate_selection(selection)
    _validate_test_lock(test_lock)
    _validate_governance(governance)
    if outputs.get("validation_report") != "outputs/metropt3_advanced_model_comparison_contract_report.json":
        raise AdvancedModelComparisonError("The governed validation-report path is incorrect.")


def load_contract(path: Path) -> dict[str, Any]:
    """Load and validate the advanced-model comparison contract."""
    payload = _read_json(path, "Advanced-model comparison contract")
    validate_contract(payload)
    return payload


def _resolve_project_path(project_root: Path, relative_path: str, label: str) -> Path:
    candidate = (project_root / relative_path).resolve()
    root = project_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise AdvancedModelComparisonError(f"{label} escapes the project root: {relative_path}")
    return candidate


def _validate_source_artifacts(contract: dict[str, Any], project_root: Path) -> dict[str, Any]:
    reference = contract["baseline_reference"]
    artifacts: list[dict[str, Any]] = []
    for category in ("committed_sources", "generated_sources"):
        for relative_path in reference[category]:
            path = _resolve_project_path(project_root, relative_path, category)
            if not path.is_file():
                raise AdvancedModelComparisonError(f"Required baseline evidence does not exist: {path}")
            if path.suffix.lower() == ".json":
                _read_json(path, f"Baseline evidence {relative_path}")
            artifacts.append({
                "category": category,
                "path": relative_path,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            })

    test_report = reference["test_report"]
    report_path = _resolve_project_path(project_root, test_report["path"], "baseline test report")
    actual_checksum = _sha256(report_path)
    if actual_checksum != test_report["sha256"]:
        raise AdvancedModelComparisonError("Finalized baseline test-report SHA-256 does not match the comparison contract.")
    return {"artifacts": artifacts, "finalized_test_report_sha256": actual_checksum}


def validate_advanced_model_comparison(
    config_path: Path,
    report_path: Path,
    *,
    project_root: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate the contract and write a no-training governance report."""
    if report_path.exists() and not overwrite:
        raise AdvancedModelComparisonError(f"Output already exists; use --overwrite: {report_path}")
    contract = load_contract(config_path)
    root = PROJECT_ROOT if project_root is None else project_root
    source_evidence = _validate_source_artifacts(contract, root)
    candidate = contract["candidate_model"]
    selection = contract["validation_selection"]
    report = {
        "status": "valid",
        "schema_version": contract["schema_version"],
        "contract": {
            "path": config_path.as_posix(),
            "sha256": _sha256(config_path),
        },
        "baseline_reference": {
            "source_commit": contract["baseline_reference"]["source_commit"],
            "family": contract["baseline_reference"]["family"],
            "retained_feature_count": contract["baseline_reference"]["retained_feature_count"],
            "selected_threshold_quantile": contract["baseline_reference"]["selected_threshold_quantile"],
            "frozen_threshold": contract["baseline_reference"]["frozen_threshold"],
            "test_evidence_design_or_tuning_use": "prohibited",
        },
        "source_evidence": source_evidence,
        "candidate_boundary": {
            "family": candidate["family"],
            "implementation": candidate["implementation"],
            "candidate_count": candidate["candidate_count"],
            "feature_count": candidate["features"]["count"],
            "threshold_quantile": candidate["alarm_threshold"]["quantile"],
            "bounded_grid": candidate["bounded_grid"],
        },
        "validation_selection": {
            "partition": selection["partition"],
            "rule": selection["rule"],
            "ordered_criteria": selection["ordered_criteria"],
            "test_evidence_available": False,
        },
        "test_lock": {
            "locked": True,
            "unlock_conditions": contract["test_lock"]["unlock_conditions"],
            "one_time_future_evaluation": True,
        },
        "scope": {
            "feature_rows_read": False,
            "learned_preprocessing_fitted": False,
            "advanced_model_fitted": False,
            "candidate_scores_generated": False,
            "candidate_alarms_generated": False,
            "candidate_selected": False,
            "advanced_test_partition_accessed": False,
            "baseline_revised": False,
            "performance_claims_reported": False,
        },
        "software": {"python_version": platform.python_version()},
    }
    write_json_atomic(report, report_path)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the MetroPT-3 advanced-model comparison contract.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    arguments = build_argument_parser().parse_args()
    try:
        report = validate_advanced_model_comparison(
            arguments.config,
            arguments.report,
            overwrite=arguments.overwrite,
        )
    except (AdvancedModelComparisonError, OSError) as error:
        print(f"ERROR: {error}")
        return 1
    print(json.dumps({
        "processing_status": "advanced_model_comparison_contract_validated",
        "candidate_family": report["candidate_boundary"]["family"],
        "candidate_count": report["candidate_boundary"]["candidate_count"],
        "advanced_test_partition_locked": report["test_lock"]["locked"],
        "report": arguments.report.as_posix(),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

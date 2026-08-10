"""Validated application configuration and project-relative path controls."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "application.json"


class ApplicationConfigError(ValueError):
    """Raised when the local application contract is unsafe or malformed."""


@dataclass(frozen=True)
class ApplicationConfig:
    """Validated immutable application settings."""

    raw: dict[str, Any]
    project_root: Path

    @property
    def api(self) -> dict[str, Any]:
        return self.raw["api"]

    @property
    def server(self) -> dict[str, Any]:
        return self.raw["server"]

    @property
    def persistence(self) -> dict[str, Any]:
        return self.raw["persistence"]

    @property
    def prediction(self) -> dict[str, Any]:
        return self.raw["prediction"]

    @property
    def knowledge(self) -> dict[str, Any]:
        return self.raw["knowledge"]

    @property
    def security(self) -> dict[str, Any]:
        return self.raw["security"]

    def resolve_path(self, relative_path: str) -> Path:
        return resolve_project_path(self.project_root, relative_path)


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ApplicationConfigError(f"{label} must be an object")
    return value


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApplicationConfigError(f"{label} must be a non-empty string")
    return value.strip()


def _require_positive_int(value: Any, label: str, *, maximum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ApplicationConfigError(f"{label} must be a positive integer")
    if maximum is not None and value > maximum:
        raise ApplicationConfigError(f"{label} must be <= {maximum}")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ApplicationConfigError(f"{label} must be boolean")
    return value


def _require_sha256(value: Any, label: str) -> str:
    text = _require_nonempty_string(value, label).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ApplicationConfigError(f"{label} must be a 64-character lowercase SHA-256")
    return text


def resolve_project_path(project_root: Path, relative_path: str) -> Path:
    """Resolve one configured path without allowing traversal outside the project root."""
    text = _require_nonempty_string(relative_path, "configured path")
    raw_path = Path(text)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise ApplicationConfigError(f"Configured path must be project-relative: {text}")
    root = Path(project_root).resolve()
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ApplicationConfigError(f"Configured path escapes project root: {text}") from error
    return candidate


def _reject_inline_secrets(value: Any, path: tuple[str, ...] = ()) -> None:
    """Reject secret-like leaf keys so committed JSON cannot become a secret store."""
    prohibited = {"password", "passwd", "token", "api_key", "apikey", "secret", "private_key"}
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ApplicationConfigError("Configuration keys must be strings")
            if key.lower() in prohibited and nested not in (None, "", [], {}):
                dotted = ".".join((*path, key))
                raise ApplicationConfigError(f"Secret material is prohibited in committed config: {dotted}")
            _reject_inline_secrets(nested, (*path, key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_inline_secrets(nested, (*path, str(index)))


def validate_config(raw: dict[str, Any], *, project_root: Path = PROJECT_ROOT) -> ApplicationConfig:
    """Validate the bounded local application contract."""
    if not isinstance(raw, dict):
        raise ApplicationConfigError("Application config root must be an object")
    if raw.get("schema_version") != 1:
        raise ApplicationConfigError("schema_version must equal 1")
    _require_nonempty_string(raw.get("application_id"), "application_id")
    _reject_inline_secrets(raw)

    api = _require_dict(raw.get("api"), "api")
    for field in ("title", "version", "prefix"):
        _require_nonempty_string(api.get(field), f"api.{field}")
    if not api["prefix"].startswith("/") or api["prefix"].endswith("/"):
        raise ApplicationConfigError("api.prefix must start with '/' and must not end with '/'")
    _require_positive_int(api.get("query_max_characters"), "api.query_max_characters", maximum=10000)
    default_top_k = _require_positive_int(api.get("retrieval_default_top_k"), "api.retrieval_default_top_k")
    max_top_k = _require_positive_int(api.get("retrieval_max_top_k"), "api.retrieval_max_top_k", maximum=100)
    if default_top_k > max_top_k:
        raise ApplicationConfigError("api.retrieval_default_top_k cannot exceed api.retrieval_max_top_k")
    history_default = _require_positive_int(api.get("history_default_limit"), "api.history_default_limit")
    history_max = _require_positive_int(api.get("history_max_limit"), "api.history_max_limit", maximum=1000)
    if history_default > history_max:
        raise ApplicationConfigError("api.history_default_limit cannot exceed api.history_max_limit")

    server = _require_dict(raw.get("server"), "server")
    host = _require_nonempty_string(server.get("host"), "server.host")
    _require_positive_int(server.get("port"), "server.port", maximum=65535)
    require_loopback = _require_bool(server.get("require_loopback_bind"), "server.require_loopback_bind")
    if require_loopback and host not in {"127.0.0.1", "localhost", "::1"}:
        raise ApplicationConfigError("server.host must be loopback when require_loopback_bind is true")

    persistence = _require_dict(raw.get("persistence"), "persistence")
    database_path = _require_nonempty_string(persistence.get("database_path"), "persistence.database_path")
    resolved_database = resolve_project_path(project_root, database_path)
    if resolved_database.suffix not in {".sqlite", ".sqlite3", ".db"}:
        raise ApplicationConfigError("persistence.database_path must use a local SQLite extension")
    _require_positive_int(persistence.get("max_records"), "persistence.max_records", maximum=100000)
    _require_positive_int(persistence.get("max_evaluations"), "persistence.max_evaluations", maximum=100000)
    _require_positive_int(persistence.get("max_events"), "persistence.max_events", maximum=200000)

    prediction = _require_dict(raw.get("prediction"), "prediction")
    for field in ("model_path", "feature_parameters_path", "validation_report_path"):
        resolve_project_path(project_root, _require_nonempty_string(prediction.get(field), f"prediction.{field}"))
    _require_sha256(prediction.get("model_sha256"), "prediction.model_sha256")
    _require_nonempty_string(prediction.get("candidate_id"), "prediction.candidate_id")
    threshold = prediction.get("threshold")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not math.isfinite(float(threshold)):
        raise ApplicationConfigError("prediction.threshold must be finite numeric")
    _require_positive_int(prediction.get("retained_feature_count"), "prediction.retained_feature_count", maximum=10000)
    if prediction.get("matrix_dtype") != "float32":
        raise ApplicationConfigError("prediction.matrix_dtype must remain float32")
    if prediction.get("threshold_comparison") != "strictly_greater_than":
        raise ApplicationConfigError("prediction.threshold_comparison must remain strictly_greater_than")

    knowledge = _require_dict(raw.get("knowledge"), "knowledge")
    for field in ("retrieval_config_path", "grounding_config_path", "chunk_path", "retrieval_index_path"):
        resolve_project_path(project_root, _require_nonempty_string(knowledge.get(field), f"knowledge.{field}"))
    _require_sha256(knowledge.get("chunk_sha256"), "knowledge.chunk_sha256")
    _require_sha256(knowledge.get("retrieval_index_sha256"), "knowledge.retrieval_index_sha256")

    security = _require_dict(raw.get("security"), "security")
    allowed_env = security.get("allowed_environment_variables")
    if not isinstance(allowed_env, list) or any(not isinstance(item, str) or not item.strip() for item in allowed_env):
        raise ApplicationConfigError("security.allowed_environment_variables must be a list of non-empty names")
    for field in (
        "persist_raw_feature_values",
        "persist_request_headers",
        "authentication_enabled",
        "public_network_exposure_allowed",
    ):
        _require_bool(security.get(field), f"security.{field}")
    if security["public_network_exposure_allowed"]:
        raise ApplicationConfigError("public network exposure is prohibited for this bounded local release")
    if security["persist_request_headers"]:
        raise ApplicationConfigError("request-header persistence is prohibited")

    return ApplicationConfig(raw=raw, project_root=Path(project_root).resolve())


def load_config(path: Path = DEFAULT_CONFIG_PATH, *, project_root: Path = PROJECT_ROOT) -> ApplicationConfig:
    """Load JSON and return a validated immutable application configuration."""
    path = Path(path)
    if not path.is_file():
        raise ApplicationConfigError(f"Application config does not exist: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ApplicationConfigError(f"Unable to read application config: {path}") from error
    return validate_config(raw, project_root=project_root)

"""Governed prediction, retrieval, grounded-answer, and readiness services."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np

from predictive_maintenance.knowledge.grounding import GroundingError, answer_query
from predictive_maintenance.knowledge.retrieval import RetrievalError, retrieve

from .config import ApplicationConfig


class ApplicationInputError(ValueError):
    """Raised for semantically invalid bounded application inputs."""


class ApplicationDependencyError(RuntimeError):
    """Raised when a governed local artifact or dependency is unavailable or invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise ApplicationDependencyError(f"Unable to read governed artifact: {path}") from error
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ApplicationDependencyError(f"{label} does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ApplicationDependencyError(f"Unable to read {label}: {path}") from error
    if not isinstance(value, dict):
        raise ApplicationDependencyError(f"{label} must contain a JSON object")
    return value


class PredictionService:
    """Read-only scorer for the already-frozen Isolation Forest release artifact."""

    def __init__(
        self,
        config: ApplicationConfig,
        *,
        model_loader: Callable[[Path], Any] = joblib.load,
    ) -> None:
        self.config = config
        self._model_loader = model_loader
        self._runtime: tuple[Any, list[str], str] | None = None

    def _load_runtime(self) -> tuple[Any, list[str], str]:
        if self._runtime is not None:
            return self._runtime
        cfg = self.config.prediction
        model_path = self.config.resolve_path(cfg["model_path"])
        parameter_path = self.config.resolve_path(cfg["feature_parameters_path"])
        validation_path = self.config.resolve_path(cfg["validation_report_path"])
        for label, path in (
            ("Frozen model", model_path),
            ("Frozen feature parameters", parameter_path),
            ("Frozen validation report", validation_path),
        ):
            if not path.is_file():
                raise ApplicationDependencyError(f"{label} does not exist: {path}")

        actual_model_sha = sha256_file(model_path)
        if actual_model_sha != cfg["model_sha256"]:
            raise ApplicationDependencyError("Frozen model SHA-256 does not match application governance")

        parameters = _read_json(parameter_path, "Frozen feature parameters")
        retained = parameters.get("retained_features")
        if not isinstance(retained, list):
            raise ApplicationDependencyError("Frozen feature parameters do not list retained_features")
        feature_names = [item.get("feature") for item in retained if isinstance(item, dict)]
        expected_count = int(cfg["retained_feature_count"])
        if (
            len(feature_names) != expected_count
            or len(set(feature_names)) != expected_count
            or any(not isinstance(name, str) or not name for name in feature_names)
        ):
            raise ApplicationDependencyError(f"Exactly {expected_count} unique frozen features are required")

        validation = _read_json(validation_path, "Frozen Isolation Forest validation report")
        if validation.get("status") != "frozen_after_validation":
            raise ApplicationDependencyError("Isolation Forest validation evidence is not frozen_after_validation")
        selected = validation.get("selection", {}).get("selected_candidate", {})
        if selected.get("candidate_id") != cfg["candidate_id"]:
            raise ApplicationDependencyError("Frozen candidate ID does not match application governance")
        threshold = selected.get("metrics", {}).get("threshold")
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
            raise ApplicationDependencyError("Frozen validation threshold is missing")
        if not math.isclose(float(threshold), float(cfg["threshold"]), rel_tol=0.0, abs_tol=0.0):
            raise ApplicationDependencyError("Frozen threshold does not match application governance")
        recorded_model_sha = validation.get("selection", {}).get("selected_model_sha256")
        if recorded_model_sha != actual_model_sha:
            raise ApplicationDependencyError("Validation evidence does not match the frozen model artifact")

        feature_hash = hashlib.sha256(("\n".join(feature_names) + "\n").encode("utf-8")).hexdigest()
        expected_feature_hash = validation.get("inputs", {}).get("retained_feature_names_sha256")
        if expected_feature_hash != feature_hash:
            raise ApplicationDependencyError("Frozen feature-name identity does not match validation evidence")

        try:
            model = self._model_loader(model_path)
        except Exception as error:
            raise ApplicationDependencyError("Unable to load frozen Isolation Forest model") from error
        if not hasattr(model, "score_samples"):
            raise ApplicationDependencyError("Frozen model does not expose score_samples()")
        if hasattr(model, "n_features_in_") and int(model.n_features_in_) != expected_count:
            raise ApplicationDependencyError("Frozen model feature count does not match governed feature count")
        self._runtime = (model, feature_names, feature_hash)
        return self._runtime

    def schema(self) -> dict[str, Any]:
        _, feature_names, feature_hash = self._load_runtime()
        return {
            "candidate_id": self.config.prediction["candidate_id"],
            "feature_count": len(feature_names),
            "feature_names": list(feature_names),
            "feature_names_sha256": feature_hash,
            "matrix_dtype": self.config.prediction["matrix_dtype"],
            "threshold": float(self.config.prediction["threshold"]),
            "threshold_comparison": self.config.prediction["threshold_comparison"],
            "interpretation": "Isolation Forest unusualness is not a failure probability.",
        }

    def predict(self, features: dict[str, float]) -> dict[str, Any]:
        if not isinstance(features, dict):
            raise ApplicationInputError("features must be an object keyed by frozen feature name")
        model, feature_names, feature_hash = self._load_runtime()
        supplied = set(features)
        expected = set(feature_names)
        if supplied != expected:
            missing = sorted(expected - supplied)
            extra = sorted(supplied - expected)
            raise ApplicationInputError(
                "Prediction features must match the frozen feature set exactly; "
                f"missing={missing}; extra={extra}"
            )
        try:
            values = np.asarray([[features[name] for name in feature_names]], dtype=np.float32)
        except (TypeError, ValueError, OverflowError) as error:
            raise ApplicationInputError("Prediction features must be numeric float32-compatible values") from error
        if values.shape != (1, len(feature_names)) or not np.isfinite(values).all():
            raise ApplicationInputError("Prediction features must contain finite values only")
        try:
            raw = np.asarray(model.score_samples(values), dtype=np.float64)
        except Exception as error:
            raise ApplicationDependencyError("Frozen model scoring failed") from error
        if raw.shape != (1,) or not np.isfinite(raw).all():
            raise ApplicationDependencyError("Frozen model returned an invalid score")
        unusualness = -float(raw[0])
        threshold = float(self.config.prediction["threshold"])
        alarm = unusualness > threshold
        return {
            "status": "scored",
            "candidate_id": self.config.prediction["candidate_id"],
            "model_sha256": self.config.prediction["model_sha256"],
            "feature_count": len(feature_names),
            "feature_names_sha256": feature_hash,
            "unusualness_score": unusualness,
            "threshold": threshold,
            "alarm": alarm,
            "interpretation": (
                "Alarm means the frozen unusualness score is strictly greater than the frozen threshold. "
                "It is not a failure probability and does not establish a verified failure state."
            ),
        }


class KnowledgeService:
    """Read-only wrapper around frozen retrieval and grounding capabilities."""

    def __init__(self, config: ApplicationConfig) -> None:
        self.config = config

    def retrieve(self, query: str, top_k: int) -> list[dict[str, Any]]:
        try:
            return retrieve(
                query,
                top_k=top_k,
                config_path=self.config.resolve_path(self.config.knowledge["retrieval_config_path"]),
                project_root=self.config.project_root,
            )
        except RetrievalError as error:
            raise ApplicationDependencyError(f"Governed retrieval failed: {error}") from error

    def answer(self, query: str) -> dict[str, Any]:
        try:
            return answer_query(
                query,
                grounding_config_path=self.config.resolve_path(self.config.knowledge["grounding_config_path"]),
                retrieval_config_path=self.config.resolve_path(self.config.knowledge["retrieval_config_path"]),
                project_root=self.config.project_root,
            )
        except GroundingError as error:
            raise ApplicationDependencyError(f"Governed grounded-answer assembly failed: {error}") from error


class ApplicationServices:
    """Container for governed application capabilities and readiness evidence."""

    def __init__(self, config: ApplicationConfig) -> None:
        self.config = config
        self.prediction = PredictionService(config)
        self.knowledge = KnowledgeService(config)

    def readiness(self) -> dict[str, Any]:
        components: dict[str, dict[str, Any]] = {}
        checks = [
            ("prediction_model", self.config.prediction["model_path"], self.config.prediction["model_sha256"]),
            ("knowledge_chunks", self.config.knowledge["chunk_path"], self.config.knowledge["chunk_sha256"]),
            (
                "retrieval_index",
                self.config.knowledge["retrieval_index_path"],
                self.config.knowledge["retrieval_index_sha256"],
            ),
        ]
        ready = True
        for name, relative, expected_sha in checks:
            path = self.config.resolve_path(relative)
            exists = path.is_file()
            sha_match = False
            if exists:
                try:
                    sha_match = sha256_file(path) == expected_sha
                except ApplicationDependencyError:
                    sha_match = False
            components[name] = {"available": exists, "sha256_match": sha_match}
            ready = ready and exists and sha_match
        for name, relative in (
            ("retrieval_config", self.config.knowledge["retrieval_config_path"]),
            ("grounding_config", self.config.knowledge["grounding_config_path"]),
            ("feature_parameters", self.config.prediction["feature_parameters_path"]),
            ("validation_report", self.config.prediction["validation_report_path"]),
        ):
            available = self.config.resolve_path(relative).is_file()
            components[name] = {"available": available}
            ready = ready and available
        return {"status": "ready" if ready else "not_ready", "components": components}

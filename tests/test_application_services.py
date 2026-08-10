"""Controlled tests for frozen prediction and knowledge service wrappers."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.application.config import validate_config
from predictive_maintenance.application.services import (
    ApplicationDependencyError,
    ApplicationInputError,
    ApplicationServices,
    KnowledgeService,
    PredictionService,
)


class FakeModel:
    n_features_in_ = 2

    def score_samples(self, matrix):
        return np.asarray([-0.7], dtype=float)


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        (self.root / "config").mkdir(parents=True)
        (self.root / "outputs").mkdir(parents=True)
        (self.root / "data" / "interim").mkdir(parents=True)
        self.model_path = self.root / "outputs" / "model.joblib"
        joblib.dump(FakeModel(), self.model_path)
        self.model_sha = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
        feature_names = ["feature_a", "feature_b"]
        feature_hash = hashlib.sha256(("\n".join(feature_names) + "\n").encode()).hexdigest()
        (self.root / "outputs" / "params.json").write_text(json.dumps({"retained_features": [{"feature": name} for name in feature_names]}), encoding="utf-8")
        (self.root / "outputs" / "validation.json").write_text(json.dumps({
            "status": "frozen_after_validation",
            "selection": {"selected_candidate": {"candidate_id": "candidate", "metrics": {"threshold": 0.6}}, "selected_model_sha256": self.model_sha},
            "inputs": {"retained_feature_names_sha256": feature_hash},
        }), encoding="utf-8")
        (self.root / "config" / "retrieval.json").write_text("{}", encoding="utf-8")
        (self.root / "config" / "grounding.json").write_text("{}", encoding="utf-8")
        self.chunk_path = self.root / "data" / "interim" / "chunks.jsonl"; self.chunk_path.write_text("chunk\n", encoding="utf-8")
        self.index_path = self.root / "data" / "interim" / "index.joblib"; self.index_path.write_bytes(b"index")
        raw = {
            "schema_version": 1, "application_id": "test",
            "api": {"title":"T","version":"1","prefix":"/api/v1","query_max_characters":1000,"retrieval_default_top_k":5,"retrieval_max_top_k":12,"history_default_limit":20,"history_max_limit":100},
            "server": {"host":"127.0.0.1","port":8000,"require_loopback_bind":True},
            "persistence": {"database_path":"data/interim/app.sqlite3","max_records":10,"max_evaluations":10,"max_events":20},
            "prediction": {"model_path":"outputs/model.joblib","model_sha256":self.model_sha,"feature_parameters_path":"outputs/params.json","validation_report_path":"outputs/validation.json","candidate_id":"candidate","threshold":0.6,"retained_feature_count":2,"matrix_dtype":"float32","threshold_comparison":"strictly_greater_than"},
            "knowledge": {"retrieval_config_path":"config/retrieval.json","grounding_config_path":"config/grounding.json","chunk_path":"data/interim/chunks.jsonl","chunk_sha256":hashlib.sha256(self.chunk_path.read_bytes()).hexdigest(),"retrieval_index_path":"data/interim/index.joblib","retrieval_index_sha256":hashlib.sha256(self.index_path.read_bytes()).hexdigest()},
            "security": {"allowed_environment_variables":[],"persist_raw_feature_values":False,"persist_request_headers":False,"authentication_enabled":False,"public_network_exposure_allowed":False},
        }
        self.config = validate_config(raw, project_root=self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_prediction_schema_uses_frozen_feature_identity(self):
        schema = PredictionService(self.config).schema()
        self.assertEqual(schema["feature_names"], ["feature_a", "feature_b"])
        self.assertEqual(schema["threshold"], 0.6)

    def test_prediction_score_uses_negative_score_samples_and_strict_threshold(self):
        result = PredictionService(self.config).predict({"feature_a": 1.0, "feature_b": 2.0})
        self.assertAlmostEqual(result["unusualness_score"], 0.7)
        self.assertTrue(result["alarm"])
        self.assertIn("not a failure probability", result["interpretation"])

    def test_prediction_rejects_missing_feature(self):
        with self.assertRaisesRegex(ApplicationInputError, "missing"):
            PredictionService(self.config).predict({"feature_a": 1.0})

    def test_prediction_rejects_nonfinite_feature(self):
        with self.assertRaisesRegex(ApplicationInputError, "finite"):
            PredictionService(self.config).predict({"feature_a": float("nan"), "feature_b": 1.0})

    def test_prediction_rejects_model_checksum_mismatch(self):
        self.model_path.write_bytes(b"changed")
        with self.assertRaisesRegex(ApplicationDependencyError, "SHA-256"):
            PredictionService(self.config).schema()

    @patch("predictive_maintenance.application.services.retrieve")
    def test_knowledge_retrieval_delegates_without_rebuild(self, mock_retrieve):
        mock_retrieve.return_value = [{"chunk_id": "c1"}]
        result = KnowledgeService(self.config).retrieve("pressure loss", 5)
        self.assertEqual(result[0]["chunk_id"], "c1")
        self.assertEqual(mock_retrieve.call_args.kwargs["top_k"], 5)

    @patch("predictive_maintenance.application.services.answer_query")
    def test_knowledge_answer_preserves_grounding_result(self, mock_answer):
        mock_answer.return_value = {"status": "insufficient_evidence", "reason_code": "no_exact_equipment_evidence"}
        result = KnowledgeService(self.config).answer("manufacturer interval")
        self.assertEqual(result["reason_code"], "no_exact_equipment_evidence")

    def test_readiness_checks_frozen_artifact_hashes(self):
        result = ApplicationServices(self.config).readiness()
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["components"]["retrieval_index"]["sha256_match"])


if __name__ == "__main__":
    unittest.main()

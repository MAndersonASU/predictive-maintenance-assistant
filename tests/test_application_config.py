"""Controlled tests for application configuration and secret/path boundaries."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.application.config import ApplicationConfigError, load_config, validate_config


class ApplicationConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        (self.root / "config").mkdir(parents=True)
        self.path = self.root / "config" / "application.json"
        self.base = {
            "schema_version": 1,
            "application_id": "test_application",
            "api": {
                "title": "Test", "version": "1.0", "prefix": "/api/v1",
                "query_max_characters": 1000, "retrieval_default_top_k": 5,
                "retrieval_max_top_k": 12, "history_default_limit": 20, "history_max_limit": 100,
            },
            "server": {"host": "127.0.0.1", "port": 8000, "require_loopback_bind": True},
            "persistence": {"database_path": "data/interim/app.sqlite3", "max_records": 10, "max_evaluations": 10, "max_events": 20},
            "prediction": {
                "model_path": "outputs/model.joblib", "model_sha256": "a" * 64,
                "feature_parameters_path": "outputs/params.json", "validation_report_path": "outputs/validation.json",
                "candidate_id": "candidate", "threshold": 0.6, "retained_feature_count": 2,
                "matrix_dtype": "float32", "threshold_comparison": "strictly_greater_than",
            },
            "knowledge": {
                "retrieval_config_path": "config/retrieval.json", "grounding_config_path": "config/grounding.json",
                "chunk_path": "data/interim/chunks.jsonl", "chunk_sha256": "b" * 64,
                "retrieval_index_path": "data/interim/index.joblib", "retrieval_index_sha256": "c" * 64,
            },
            "security": {
                "allowed_environment_variables": [], "persist_raw_feature_values": False,
                "persist_request_headers": False, "authentication_enabled": False,
                "public_network_exposure_allowed": False,
            },
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write(self, value: dict) -> None:
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def test_valid_config_loads(self):
        self._write(self.base)
        self.assertEqual(load_config(self.path, project_root=self.root).raw["application_id"], "test_application")

    def test_path_traversal_is_rejected(self):
        value = copy.deepcopy(self.base); value["persistence"]["database_path"] = "../outside.sqlite3"
        with self.assertRaisesRegex(ApplicationConfigError, "project-relative"):
            validate_config(value, project_root=self.root)

    def test_non_loopback_bind_is_rejected(self):
        value = copy.deepcopy(self.base); value["server"]["host"] = "0.0.0.0"
        with self.assertRaisesRegex(ApplicationConfigError, "loopback"):
            validate_config(value, project_root=self.root)

    def test_public_network_exposure_is_rejected(self):
        value = copy.deepcopy(self.base); value["security"]["public_network_exposure_allowed"] = True
        with self.assertRaisesRegex(ApplicationConfigError, "public network exposure"):
            validate_config(value, project_root=self.root)

    def test_inline_secret_is_rejected(self):
        value = copy.deepcopy(self.base); value["security"]["token"] = "do-not-commit"
        with self.assertRaisesRegex(ApplicationConfigError, "Secret material"):
            validate_config(value, project_root=self.root)

    def test_raw_header_persistence_is_rejected(self):
        value = copy.deepcopy(self.base); value["security"]["persist_request_headers"] = True
        with self.assertRaisesRegex(ApplicationConfigError, "header persistence"):
            validate_config(value, project_root=self.root)

    def test_default_top_k_cannot_exceed_maximum(self):
        value = copy.deepcopy(self.base); value["api"]["retrieval_default_top_k"] = 13
        with self.assertRaisesRegex(ApplicationConfigError, "cannot exceed"):
            validate_config(value, project_root=self.root)


if __name__ == "__main__":
    unittest.main()

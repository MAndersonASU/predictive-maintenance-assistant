"""Integration tests for HTTP contracts, persistence, health, and failure-safe responses."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.application.api import create_app
from predictive_maintenance.application.config import validate_config
from predictive_maintenance.application.persistence import SQLiteStore
from predictive_maintenance.application.services import ApplicationDependencyError, ApplicationInputError


class FakePrediction:
    def schema(self):
        return {"candidate_id":"candidate","feature_count":2,"feature_names":["a","b"],"feature_names_sha256":"f"*64,"matrix_dtype":"float32","threshold":0.6,"threshold_comparison":"strictly_greater_than","interpretation":"Isolation Forest unusualness is not a failure probability."}

    def predict(self, features):
        if set(features) != {"a", "b"}:
            raise ApplicationInputError("Prediction features must match the frozen feature set exactly")
        return {"status":"scored","candidate_id":"candidate","model_sha256":"a"*64,"feature_count":2,"feature_names_sha256":"f"*64,"unusualness_score":0.7,"threshold":0.6,"alarm":True,"interpretation":"Alarm is unusualness, not a failure probability."}


class FakeKnowledge:
    def retrieve(self, query, top_k):
        if query == "dependency failure":
            raise ApplicationDependencyError("controlled")
        return [{"rank":1,"chunk_id":"c1","classification":"authoritative_general_reference","locator":"page:1","text":"Controlled evidence."}]

    def answer(self, query):
        return {"schema_version":1,"status":"insufficient_evidence","reason_code":"no_exact_equipment_evidence","intent":"equipment_specific","answer":"Insufficient governed evidence.","citations":[],"evidence_chunk_count":0,"general_guidance_available":True,"grounding_id":"g1","grounding_config_sha256":"b"*64,"retrieval_candidate_count":2,"reranked_candidate_count":2,"top_reranked":[]}


class FakeServices:
    def __init__(self):
        self.prediction = FakePrediction(); self.knowledge = FakeKnowledge()

    def readiness(self):
        return {"status":"ready","components":{"prediction_model":{"available":True,"sha256_match":True}}}


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"; (self.root / "data" / "interim").mkdir(parents=True)
        raw = {
            "schema_version":1,"application_id":"test_app",
            "api":{"title":"Test API","version":"1","prefix":"/api/v1","query_max_characters":50,"retrieval_default_top_k":5,"retrieval_max_top_k":12,"history_default_limit":20,"history_max_limit":100},
            "server":{"host":"127.0.0.1","port":8000,"require_loopback_bind":True},
            "persistence":{"database_path":"data/interim/app.sqlite3","max_records":50,"max_evaluations":50,"max_events":100},
            "prediction":{"model_path":"outputs/m.joblib","model_sha256":"a"*64,"feature_parameters_path":"outputs/p.json","validation_report_path":"outputs/v.json","candidate_id":"candidate","threshold":0.6,"retained_feature_count":2,"matrix_dtype":"float32","threshold_comparison":"strictly_greater_than"},
            "knowledge":{"retrieval_config_path":"config/r.json","grounding_config_path":"config/g.json","chunk_path":"data/interim/c.jsonl","chunk_sha256":"b"*64,"retrieval_index_path":"data/interim/i.joblib","retrieval_index_sha256":"c"*64},
            "security":{"allowed_environment_variables":[],"persist_raw_feature_values":False,"persist_request_headers":False,"authentication_enabled":False,"public_network_exposure_allowed":False},
        }
        self.config = validate_config(raw, project_root=self.root)
        self.store = SQLiteStore(self.config.resolve_path(self.config.persistence["database_path"]), max_records=50, max_evaluations=50, max_events=100)
        self.app = create_app(config=self.config, services=FakeServices(), store=self.store)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    def test_liveness_and_request_id_header(self):
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")
        self.assertEqual(len(response.headers["X-Request-ID"]), 32)

    def test_readiness_includes_persistence(self):
        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["persistence"]["available"])

    def test_prediction_contract_and_redacted_persistence(self):
        response = self.client.post("/api/v1/predict", json={"features":{"a":1.0,"b":2.0}})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["alarm"])
        record = self.store.recent_records(limit=1)[0]
        self.assertFalse(record["request"]["raw_feature_values_persisted"])
        self.assertNotIn("features", record["request"])

    def test_retrieval_contract_persists_summary_not_full_results(self):
        response = self.client.post("/api/v1/retrieve", json={"query":"pressure","top_k":3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result_count"], 1)
        record = self.store.recent_records(limit=1)[0]
        self.assertEqual(record["response"], {"result_count": 1})

    def test_grounded_answer_preserves_refusal_reason(self):
        response = self.client.post("/api/v1/answer", json={"query":"manufacturer interval"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reason_code"], "no_exact_equipment_evidence")

    def test_unknown_request_field_is_rejected_without_echoing_value(self):
        response = self.client.post("/api/v1/retrieve", json={"query":"pressure","extra":"sensitive-value"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error_code"], "invalid_request")
        self.assertNotIn("sensitive-value", response.text)

    def test_query_length_limit_is_failure_safe(self):
        response = self.client.post("/api/v1/retrieve", json={"query":"x"*51})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error_code"], "invalid_application_input")

    def test_dependency_failure_is_sanitized(self):
        response = self.client.post("/api/v1/retrieve", json={"query":"dependency failure"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error_code"], "governed_dependency_unavailable")
        self.assertNotIn("controlled", response.text)

    def test_local_evaluation_record_is_bounded_review_evidence(self):
        response = self.client.post(
            "/api/v1/evaluations",
            json={"operation":"answer","outcome":"needs_review","note":"Check citation presentation."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("not_model_or_rag_benchmark_evidence", response.json()["scope"])
        history = self.client.get("/api/v1/evaluations?limit=1")
        self.assertEqual(history.json()["evaluation_count"], 1)
        self.assertEqual(history.json()["evaluations"][0]["outcome"], "needs_review")

    def test_history_is_bounded_and_metrics_are_visible(self):
        self.client.post("/api/v1/retrieve", json={"query":"pressure"})
        history = self.client.get("/api/v1/history?limit=1")
        metrics = self.client.get("/api/v1/metrics")
        self.assertEqual(history.status_code, 200)
        self.assertLessEqual(history.json()["record_count"], 1)
        self.assertGreaterEqual(metrics.json()["counters"]["retrieval_requests_total"], 1)

    def test_openapi_documents_primary_application_paths(self):
        document = self.client.get("/openapi.json").json()
        for path in ("/api/v1/predict", "/api/v1/retrieve", "/api/v1/answer", "/api/v1/evaluations", "/health/ready"):
            self.assertIn(path, document["paths"])

    def test_demo_to_api_path_is_functionally_integrated(self):
        interface = self.client.get("/")
        schema = self.client.get("/api/v1/prediction/schema")
        prediction = self.client.post("/api/v1/predict", json={"features":{"a":1.0,"b":2.0}})
        retrieval = self.client.post("/api/v1/retrieve", json={"query":"pressure","top_k":3})
        answer = self.client.post("/api/v1/answer", json={"query":"manufacturer interval"})

        self.assertEqual(interface.status_code, 200)
        self.assertEqual(schema.json()["feature_count"], 2)
        self.assertTrue(prediction.json()["alarm"])
        self.assertEqual(retrieval.json()["results"][0]["chunk_id"], "c1")
        self.assertEqual(answer.json()["reason_code"], "no_exact_equipment_evidence")


if __name__ == "__main__":
    unittest.main()

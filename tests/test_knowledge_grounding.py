"""Controlled tests for deterministic reranking and citation-grounded answers."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.knowledge.grounding import (
    GroundingError,
    answer_query,
    assemble_answer,
    detect_intent,
    load_config,
    rerank,
    validate_config,
    validate_grounding,
)


class KnowledgeGroundingTests(unittest.TestCase):
    """Verify bounded reranking, provenance, citations, and refusal behavior."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        (self.root / "config").mkdir(parents=True)
        (self.root / "outputs").mkdir(parents=True)
        self.config_path = self.root / "config" / "knowledge_grounding.json"
        self.retrieval_config_path = self.root / "config" / "knowledge_retrieval.json"
        self.retrieval_config_path.write_text("{}\n", encoding="utf-8")
        self.base_config = {
            "schema_version": 1,
            "grounding_id": "controlled_grounding",
            "report_path": "outputs/knowledge_grounding_report.json",
            "retrieval": {"candidate_k": 5},
            "reranking": {
                "hybrid_weight": 0.55,
                "coverage_weight": 0.30,
                "phrase_weight": 0.10,
                "classification_weight": 0.05,
                "minimum_rerank_score": 0.08,
                "max_evidence_chunks": 3,
            },
            "answer": {
                "max_sentences_per_chunk": 2,
                "max_total_sentences": 4,
                "minimum_evidence_chunks": 1,
                "citation_prefix": "S",
                "exact_equipment_classification": "exact_equipment_source",
                "exact_dataset_classification": "exact_dataset_source",
                "general_classification": "authoritative_general_reference",
                "equipment_specific_markers": [
                    "metropt compressor",
                    "this compressor",
                    "manufacturer-specified",
                    "service manual",
                    "exact equipment",
                ],
                "dataset_specific_markers": ["metropt", "dataset", "uci", "sensor data"],
                "insufficient_evidence_message": (
                    "Insufficient governed evidence to answer this request safely."
                ),
            },
        }
        self._write_config(self.base_config)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_config(self, value: dict) -> None:
        self.config_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def _candidate(
        self, index: int, text: str, *,
        classification: str = "authoritative_general_reference",
        hybrid_score: float = 0.5,
        source_id: str = "general_reference",
    ) -> dict:
        return {
            "rank": index, "hybrid_score": hybrid_score, "vector_score": hybrid_score,
            "keyword_score": hybrid_score, "chunk_id": f"{source_id}::{index:04d}",
            "source_id": source_id, "source_title": "Controlled Compressor Reference",
            "publisher": "Controlled Publisher", "source_url": "https://example.invalid/reference",
            "doi": "", "classification": classification,
            "equipment_relevance": "Controlled evidence scope.",
            "license_or_usage_status": "Controlled test fixture.",
            "retrieval_identity": "controlled", "scope_note": "Scope remains explicit.",
            "source_sha256": "a" * 64, "locator": f"page:{index}",
            "unit_index": index, "unit_chunk_index": 1, "source_chunk_index": index,
            "word_count": len(text.split()), "text_sha256": f"{index:064x}"[-64:], "text": text,
        }

    def test_valid_config_loads(self):
        self.assertEqual(load_config(self.config_path)["grounding_id"], "controlled_grounding")

    def test_reranking_weights_must_sum_to_one(self):
        config = copy.deepcopy(self.base_config); config["reranking"]["hybrid_weight"] = 0.70
        with self.assertRaisesRegex(GroundingError, "weights must sum"): validate_config(config)

    def test_report_path_must_be_project_relative(self):
        config = copy.deepcopy(self.base_config); config["report_path"] = "../outside.json"
        with self.assertRaisesRegex(GroundingError, "project-relative"): validate_config(config)

    def test_candidate_k_must_be_positive(self):
        config = copy.deepcopy(self.base_config); config["retrieval"]["candidate_k"] = 0
        with self.assertRaisesRegex(GroundingError, "candidate_k"): validate_config(config)

    def test_detects_dataset_intent(self):
        self.assertEqual(detect_intent("What sensors are in the MetroPT dataset?", self.base_config), "dataset_specific")

    def test_detects_equipment_specific_intent_before_dataset_intent(self):
        self.assertEqual(detect_intent("What is the manufacturer-specified interval for the MetroPT compressor?", self.base_config), "equipment_specific")

    def test_general_query_stays_general(self):
        self.assertEqual(detect_intent("How can compressed-air leaks waste energy?", self.base_config), "general")

    def test_empty_query_is_rejected(self):
        with self.assertRaisesRegex(GroundingError, "non-empty"): detect_intent("   ", self.base_config)

    def test_reranking_is_deterministic(self):
        candidates = [self._candidate(1, "Pressure losses can result from leaks in compressed air systems.", hybrid_score=0.5), self._candidate(2, "Lubrication inspection supports preventive maintenance.", hybrid_score=0.5)]
        first = rerank("compressed air pressure leaks", candidates, self.base_config)
        second = rerank("compressed air pressure leaks", candidates, self.base_config)
        self.assertEqual([(r["chunk_id"], r["rerank_score"]) for r in first], [(r["chunk_id"], r["rerank_score"]) for r in second])

    def test_reranking_uses_query_coverage(self):
        candidates = [self._candidate(1, "Pressure losses can result from leaks in compressed air systems.", hybrid_score=0.4), self._candidate(2, "Lubrication inspection supports preventive maintenance.", hybrid_score=0.6)]
        self.assertEqual(rerank("compressed air pressure leaks", candidates, self.base_config)[0]["chunk_id"], candidates[0]["chunk_id"])

    def test_reranking_preserves_original_source_classification(self):
        c = self._candidate(1, "MetroPT records pressure and temperature sensor values.", classification="exact_dataset_source", source_id="metropt")
        r = rerank("MetroPT sensor data", [c], self.base_config)[0]
        self.assertEqual((r["classification"], r["source_id"], r["locator"]), ("exact_dataset_source", "metropt", "page:1"))

    def test_reranking_exposes_component_scores_and_two_ranks(self):
        r = rerank("compressed air pressure", [self._candidate(2, "Compressed air pressure maintenance guidance.")], self.base_config)[0]
        self.assertEqual((r["retrieval_rank"], r["rerank_rank"]), (2, 1))
        self.assertIn("query_coverage", r["rerank_components"])

    def test_general_answer_contains_stable_citation(self):
        c = self._candidate(1, "Compressed air leaks increase system losses. Pressure drop should be investigated.", hybrid_score=0.8)
        result = assemble_answer("compressed air leaks pressure", rerank("compressed air leaks pressure", [c], self.base_config), self.base_config)
        self.assertEqual(result["status"], "answered"); self.assertIn("[S1]", result["answer"])
        self.assertEqual(result["citations"][0]["locator"], "page:1")

    def test_dataset_answer_labels_dataset_evidence(self):
        c = self._candidate(1, "MetroPT records pressure temperature and motor current for predictive maintenance.", classification="exact_dataset_source", source_id="metropt", hybrid_score=0.8)
        result = assemble_answer("MetroPT dataset sensor data", rerank("MetroPT dataset sensor data", [c], self.base_config), self.base_config)
        self.assertTrue(result["answer"].startswith("Governed dataset evidence:"))

    def test_equipment_specific_request_refuses_general_evidence(self):
        c = self._candidate(1, "General compressor lubrication practices depend on equipment design.", hybrid_score=0.9)
        q = "What is the manufacturer-specified interval for the MetroPT compressor?"
        result = assemble_answer(q, rerank(q, [c], self.base_config), self.base_config)
        self.assertEqual(result["reason_code"], "no_exact_equipment_evidence")
        self.assertIn("not verified as the exact equipment manual", result["answer"])

    def test_equipment_specific_request_can_answer_exact_equipment_fixture(self):
        c = self._candidate(1, "The exact equipment service manual specifies inspection every 500 operating hours.", classification="exact_equipment_source", source_id="exact_manual", hybrid_score=0.9)
        q = "What does the service manual specify for this compressor?"
        result = assemble_answer(q, rerank(q, [c], self.base_config), self.base_config)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["citations"][0]["classification"], "exact_equipment_source")

    def test_no_candidates_returns_insufficient_evidence(self):
        self.assertEqual(assemble_answer("general maintenance guidance", [], self.base_config)["reason_code"], "below_evidence_threshold")

    def test_low_rerank_score_is_rejected(self):
        config = copy.deepcopy(self.base_config); config["reranking"]["minimum_rerank_score"] = 0.95
        c = self._candidate(1, "Unrelated compressor text.", hybrid_score=0.1)
        self.assertEqual(assemble_answer("pressure leakage efficiency", rerank("pressure leakage efficiency", [c], config), config)["status"], "insufficient_evidence")

    def test_evidence_chunk_count_is_bounded(self):
        candidates = [self._candidate(i, f"Compressed air leak pressure maintenance evidence {i}.", hybrid_score=0.8) for i in range(1, 6)]
        result = assemble_answer("compressed air leak pressure maintenance", rerank("compressed air leak pressure maintenance", candidates, self.base_config), self.base_config)
        self.assertLessEqual(len(result["citations"]), 3)

    @patch("predictive_maintenance.knowledge.grounding.retrieve")
    def test_answer_query_uses_bounded_candidate_k(self, mock_retrieve):
        mock_retrieve.return_value = [self._candidate(1, "Compressed air leaks increase pressure losses.", hybrid_score=0.8)]
        result = answer_query("compressed air leaks", grounding_config_path=self.config_path, retrieval_config_path=self.retrieval_config_path, project_root=self.root)
        self.assertEqual(mock_retrieve.call_args.kwargs["top_k"], 5)
        self.assertEqual(result["retrieval_candidate_count"], 1)

    @patch("predictive_maintenance.knowledge.grounding.retrieve")
    def test_answer_query_propagates_grounding_identity(self, mock_retrieve):
        mock_retrieve.return_value = [self._candidate(1, "Compressed air leaks increase pressure losses.", hybrid_score=0.8)]
        result = answer_query("compressed air leaks", grounding_config_path=self.config_path, retrieval_config_path=self.retrieval_config_path, project_root=self.root)
        self.assertEqual(result["grounding_id"], "controlled_grounding")
        self.assertEqual(len(result["grounding_config_sha256"]), 64)

    @patch("predictive_maintenance.knowledge.grounding.answer_query")
    def test_validation_report_keeps_evaluation_scope_separate(self, mock_answer):
        def fake(query, **kwargs):
            if "manufacturer-specified" in query:
                return {"status": "insufficient_evidence", "reason_code": "no_exact_equipment_evidence", "intent": "equipment_specific", "citations": []}
            classification = "exact_dataset_source" if "MetroPT" in query else "authoritative_general_reference"
            return {"status": "answered", "reason_code": "grounded", "intent": "dataset_specific" if "MetroPT" in query else "general", "citations": [{"classification": classification}]}
        mock_answer.side_effect = fake
        report = validate_grounding(grounding_config_path=self.config_path, retrieval_config_path=self.retrieval_config_path, project_root=self.root)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["retrieval_index_modified"])
        self.assertIn("not formally evaluated", report["evaluation_scope"])

    @patch("predictive_maintenance.knowledge.grounding.answer_query")
    def test_validation_report_fails_when_expected_refusal_does_not_occur(self, mock_answer):
        mock_answer.return_value = {"status": "answered", "reason_code": "grounded", "intent": "general", "citations": [{"classification": "authoritative_general_reference"}]}
        report = validate_grounding(grounding_config_path=self.config_path, retrieval_config_path=self.retrieval_config_path, project_root=self.root)
        self.assertEqual(report["status"], "failed")

    def test_missing_candidate_provenance_is_rejected(self):
        c = self._candidate(1, "Compressed air pressure evidence."); del c["locator"]
        with self.assertRaisesRegex(GroundingError, "missing field"): rerank("compressed air pressure", [c], self.base_config)


if __name__ == "__main__":
    unittest.main()

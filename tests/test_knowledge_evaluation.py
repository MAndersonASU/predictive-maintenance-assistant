"""Controlled tests for governed retrieval and RAG evaluation."""

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

from predictive_maintenance.knowledge.evaluation import (
    EvaluationError,
    aggregate_results,
    evaluate_case,
    load_config,
    run_evaluation,
    validate_config,
    validate_frozen_artifacts,
)


class KnowledgeEvaluationTests(unittest.TestCase):
    """Verify dimension separation, frozen identity, and failure visibility."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        (self.root / "config").mkdir(parents=True)
        (self.root / "outputs").mkdir(parents=True)
        self.config_path = self.root / "config" / "knowledge_evaluation.json"
        self.retrieval_config_path = self.root / "config" / "knowledge_retrieval.json"
        self.grounding_config_path = self.root / "config" / "knowledge_grounding.json"
        self.retrieval_config_path.write_text("{}\n", encoding="utf-8")
        self.grounding_config_path.write_text("{}\n", encoding="utf-8")

        self.base_case = {
            "case_id": "general_leaks",
            "category": "general_guidance",
            "query": "Why are compressed-air leaks important maintenance targets?",
            "expected_status": "answered",
            "expected_reason_code": "grounded",
            "expected_intent": "general",
            "relevant_source_ids": ["doe"],
            "expected_source_classifications": ["authoritative_general_reference"],
            "required_concepts": [["leak", "leaks"], ["energy", "loss"]],
        }
        self.boundary_case = {
            "case_id": "equipment_interval",
            "category": "equipment_boundary",
            "query": "What is the manufacturer-specified interval for the MetroPT compressor?",
            "expected_status": "insufficient_evidence",
            "expected_reason_code": "no_exact_equipment_evidence",
            "expected_intent": "equipment_specific",
            "relevant_source_ids": [],
            "expected_source_classifications": [],
            "required_concepts": [],
        }
        self.base_config = {
            "schema_version": 1,
            "evaluation_id": "controlled_rag_evaluation",
            "report_path": "outputs/knowledge_evaluation_report.json",
            "frozen_artifacts": {
                "corpus_id": "controlled_corpus",
                "retrieval_id": "controlled_retrieval",
                "grounding_id": "controlled_grounding",
                "expected_chunk_sha256": "a" * 64,
                "expected_retrieval_index_sha256": "b" * 64,
            },
            "retrieval": {
                "evaluation_top_k": 5,
                "metric_cutoffs": [1, 3, 5],
            },
            "usefulness": {"minimum_concept_coverage": 0.5},
            "cases": [copy.deepcopy(self.base_case), copy.deepcopy(self.boundary_case)],
            "limitations": ["bounded set", "source-level relevance", "proxy usefulness"],
        }
        self._write_config(self.base_config)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_config(self, value: dict) -> None:
        self.config_path.write_text(
            json.dumps(value, indent=2) + "\n",
            encoding="utf-8",
        )

    def _candidate(
        self,
        rank: int = 1,
        *,
        source_id: str = "doe",
        classification: str = "authoritative_general_reference",
        text: str = "Compressed air leaks waste energy and increase system losses.",
        chunk_id: str | None = None,
    ) -> dict:
        chunk_id = chunk_id or f"{source_id}::{rank:04d}"
        return {
            "rank": rank,
            "hybrid_score": 0.8,
            "vector_score": 0.8,
            "keyword_score": 0.8,
            "chunk_id": chunk_id,
            "source_id": source_id,
            "source_title": "Controlled Source",
            "publisher": "Controlled Publisher",
            "source_url": "https://example.invalid/source",
            "classification": classification,
            "scope_note": "Controlled scope.",
            "locator": f"page:{rank}",
            "text_sha256": f"{rank:064x}"[-64:],
            "text": text,
            "rerank_score": 0.9,
            "retrieval_rank": rank,
            "rerank_rank": rank,
        }

    def _answer(self, candidate: dict | None = None) -> dict:
        candidate = candidate or self._candidate()
        return {
            "status": "answered",
            "reason_code": "grounded",
            "intent": "general",
            "answer": (
                "Authoritative general guidance: "
                "Compressed air leaks waste energy and increase system losses. [S1]"
            ),
            "citations": [
                {
                    "citation_id": "S1",
                    "chunk_id": candidate["chunk_id"],
                    "source_id": candidate["source_id"],
                    "classification": candidate["classification"],
                    "locator": candidate["locator"],
                    "text_sha256": candidate["text_sha256"],
                }
            ],
        }

    def _refusal(self) -> dict:
        return {
            "status": "insufficient_evidence",
            "reason_code": "no_exact_equipment_evidence",
            "intent": "equipment_specific",
            "answer": "Insufficient governed evidence to answer this request safely.",
            "citations": [],
        }

    def test_valid_config_loads(self):
        loaded = load_config(self.config_path)
        self.assertEqual(loaded["evaluation_id"], "controlled_rag_evaluation")

    def test_schema_version_is_fixed(self):
        config = copy.deepcopy(self.base_config)
        config["schema_version"] = 2
        with self.assertRaisesRegex(EvaluationError, "schema_version"):
            validate_config(config)

    def test_report_path_must_be_project_relative(self):
        config = copy.deepcopy(self.base_config)
        config["report_path"] = "../outside.json"
        with self.assertRaisesRegex(EvaluationError, "project-relative"):
            validate_config(config)

    def test_frozen_hash_must_be_lowercase_sha256(self):
        config = copy.deepcopy(self.base_config)
        config["frozen_artifacts"]["expected_chunk_sha256"] = "NOT-A-HASH"
        with self.assertRaisesRegex(EvaluationError, "SHA-256"):
            validate_config(config)

    def test_metric_cutoffs_must_be_sorted_unique(self):
        config = copy.deepcopy(self.base_config)
        config["retrieval"]["metric_cutoffs"] = [3, 1, 3]
        with self.assertRaisesRegex(EvaluationError, "unique and sorted"):
            validate_config(config)

    def test_metric_cutoff_cannot_exceed_top_k(self):
        config = copy.deepcopy(self.base_config)
        config["retrieval"]["metric_cutoffs"] = [1, 6]
        with self.assertRaisesRegex(EvaluationError, "cannot exceed"):
            validate_config(config)

    def test_duplicate_case_ids_are_rejected(self):
        config = copy.deepcopy(self.base_config)
        config["cases"].append(copy.deepcopy(config["cases"][0]))
        with self.assertRaisesRegex(EvaluationError, "Duplicate case_id"):
            validate_config(config)

    def test_answerable_case_requires_relevant_source(self):
        config = copy.deepcopy(self.base_config)
        config["cases"][0]["relevant_source_ids"] = []
        with self.assertRaisesRegex(EvaluationError, "need relevant_source_ids"):
            validate_config(config)

    def test_boundary_case_cannot_claim_exact_source(self):
        config = copy.deepcopy(self.base_config)
        config["cases"][1]["relevant_source_ids"] = ["manual"]
        with self.assertRaisesRegex(EvaluationError, "equipment_boundary"):
            validate_config(config)

    def test_limitations_are_required(self):
        config = copy.deepcopy(self.base_config)
        config["limitations"] = ["one"]
        with self.assertRaisesRegex(EvaluationError, "at least three"):
            validate_config(config)

    def test_retrieval_hit_and_reciprocal_rank(self):
        first = self._candidate(1, source_id="other")
        second = self._candidate(2, source_id="doe")
        result = evaluate_case(
            self.base_case, [first, second], [second, first], self._answer(second),
            self.base_config
        )
        self.assertFalse(result["retrieval"]["source_hit_at_1"])
        self.assertTrue(result["retrieval"]["source_hit_at_3"])
        self.assertEqual(result["retrieval"]["first_relevant_source_rank"], 2)
        self.assertEqual(result["retrieval"]["reciprocal_rank"], 0.5)

    def test_retrieval_miss_is_visible_failure(self):
        other = self._candidate(1, source_id="other")
        answer = self._answer(other)
        result = evaluate_case(
            self.base_case, [other], [other], answer, self.base_config
        )
        self.assertIn("retrieval_source_miss_at_5", result["failure_flags"])

    def test_top1_classification_mismatch_is_visible(self):
        wrong = self._candidate(1, classification="exact_dataset_source")
        result = evaluate_case(
            self.base_case, [wrong], [wrong], self._answer(wrong), self.base_config
        )
        self.assertIn(
            "retrieval_top1_classification_mismatch", result["failure_flags"]
        )

    def test_citation_traceability_is_exact(self):
        candidate = self._candidate()
        result = evaluate_case(
            self.base_case, [candidate], [candidate], self._answer(candidate),
            self.base_config
        )
        self.assertEqual(result["citation_correctness"]["traceability_rate"], 1.0)

    def test_tampered_citation_is_detected(self):
        candidate = self._candidate()
        answer = self._answer(candidate)
        answer["citations"][0]["locator"] = "page:999"
        result = evaluate_case(
            self.base_case, [candidate], [candidate], answer, self.base_config
        )
        self.assertEqual(result["citation_correctness"]["traceability_rate"], 0.0)
        self.assertIn("citation_traceability_failure", result["failure_flags"])

    def test_missing_marker_is_detected(self):
        candidate = self._candidate()
        answer = self._answer(candidate)
        answer["answer"] = answer["answer"].replace(" [S1]", "")
        result = evaluate_case(
            self.base_case, [candidate], [candidate], answer, self.base_config
        )
        self.assertFalse(result["citation_correctness"]["marker_coverage"])
        self.assertIn("citation_marker_coverage_failure", result["failure_flags"])

    def test_extractively_supported_claim_is_faithful(self):
        candidate = self._candidate()
        result = evaluate_case(
            self.base_case, [candidate], [candidate], self._answer(candidate),
            self.base_config
        )
        self.assertEqual(
            result["faithfulness"]["supported_cited_claim_rate"], 1.0
        )

    def test_unsupported_claim_is_flagged(self):
        candidate = self._candidate()
        answer = self._answer(candidate)
        answer["answer"] = (
            "Authoritative general guidance: "
            "A fictional unsupported maintenance claim. [S1]"
        )
        result = evaluate_case(
            self.base_case, [candidate], [candidate], answer, self.base_config
        )
        self.assertEqual(
            result["faithfulness"]["supported_cited_claim_rate"], 0.0
        )
        self.assertIn("unsupported_cited_claim", result["failure_flags"])

    def test_concept_coverage_is_separate_from_faithfulness(self):
        candidate = self._candidate(
            text="Compressed air leaks should be inspected regularly."
        )
        answer = self._answer(candidate)
        answer["answer"] = (
            "Authoritative general guidance: "
            "Compressed air leaks should be inspected regularly. [S1]"
        )
        result = evaluate_case(
            self.base_case, [candidate], [candidate], answer, self.base_config
        )
        self.assertEqual(result["faithfulness"]["supported_cited_claim_rate"], 1.0)
        self.assertEqual(result["answer_usefulness"]["concept_coverage"], 0.5)

    def test_low_concept_coverage_is_visible_failure(self):
        candidate = self._candidate(text="Routine inspection is recommended.")
        answer = self._answer(candidate)
        answer["answer"] = "Authoritative general guidance: Routine inspection is recommended. [S1]"
        result = evaluate_case(
            self.base_case, [candidate], [candidate], answer, self.base_config
        )
        self.assertIn("low_usefulness_concept_coverage", result["failure_flags"])

    def test_equipment_refusal_boundary_passes_without_citations(self):
        candidate = self._candidate(
            classification="authoritative_general_reference",
            source_id="doe",
        )
        result = evaluate_case(
            self.boundary_case, [candidate], [candidate], self._refusal(),
            self.base_config
        )
        self.assertTrue(
            result["faithfulness"]["equipment_refusal_boundary_pass"]
        )
        self.assertTrue(result["answer_usefulness"]["usefulness_proxy_pass"])

    def test_equipment_refusal_can_expose_contextual_citations_without_markers(self):
        candidate = self._candidate(
            classification="authoritative_general_reference",
            source_id="doe",
        )
        refusal = self._refusal()
        refusal["citations"] = [
            {
                "citation_id": "S1",
                "chunk_id": candidate["chunk_id"],
                "source_id": candidate["source_id"],
                "classification": candidate["classification"],
                "locator": candidate["locator"],
                "text_sha256": candidate["text_sha256"],
            }
        ]
        result = evaluate_case(
            self.boundary_case, [candidate], [candidate], refusal,
            self.base_config
        )
        self.assertIsNone(result["citation_correctness"]["marker_coverage"])
        self.assertEqual(result["citation_correctness"]["traceability_rate"], 1.0)
        self.assertNotIn(
            "citation_marker_coverage_failure", result["failure_flags"]
        )
        self.assertTrue(
            result["faithfulness"]["equipment_refusal_boundary_pass"]
        )

    def test_marker_coverage_aggregate_excludes_refusal_metadata_citations(self):
        candidate = self._candidate()
        answered = evaluate_case(
            self.base_case, [candidate], [candidate], self._answer(candidate),
            self.base_config
        )
        refusal = self._refusal()
        refusal["citations"] = [
            {
                "citation_id": "S1",
                "chunk_id": candidate["chunk_id"],
                "source_id": candidate["source_id"],
                "classification": candidate["classification"],
                "locator": candidate["locator"],
                "text_sha256": candidate["text_sha256"],
            }
        ]
        boundary = evaluate_case(
            self.boundary_case, [candidate], [candidate], refusal,
            self.base_config
        )
        report = aggregate_results(
            [answered, boundary],
            {"retrieval_index_modified": False},
            self.base_config,
        )
        self.assertEqual(
            report["citation_correctness"]["marker_coverage_case_rate"], 1.0
        )

    def test_equipment_answer_is_boundary_failure(self):
        candidate = self._candidate()
        answer = self._answer(candidate)
        answer["intent"] = "equipment_specific"
        result = evaluate_case(
            self.boundary_case, [candidate], [candidate], answer,
            self.base_config
        )
        self.assertIn(
            "equipment_refusal_boundary_failure", result["failure_flags"]
        )
        self.assertIn("unexpected_answer_status", result["failure_flags"])

    def test_aggregate_keeps_dimensions_separate(self):
        candidate = self._candidate()
        general_result = evaluate_case(
            self.base_case, [candidate], [candidate], self._answer(candidate),
            self.base_config
        )
        boundary_result = evaluate_case(
            self.boundary_case, [candidate], [candidate], self._refusal(),
            self.base_config
        )
        report = aggregate_results(
            [general_result, boundary_result],
            {"retrieval_index_modified": False},
            self.base_config,
        )
        self.assertIn("retrieval_quality", report)
        self.assertIn("citation_correctness", report)
        self.assertIn("faithfulness", report)
        self.assertIn("answer_usefulness", report)
        self.assertEqual(report["status"], "completed")

    def test_aggregate_preserves_failure_cases(self):
        wrong = self._candidate(1, source_id="other")
        bad = evaluate_case(
            self.base_case, [wrong], [wrong], self._answer(wrong),
            self.base_config
        )
        report = aggregate_results(
            [bad],
            {"retrieval_index_modified": False},
            self.base_config,
        )
        self.assertEqual(report["failure_case_count"], 1)
        self.assertEqual(report["failure_cases"][0]["case_id"], "general_leaks")

    @patch("predictive_maintenance.knowledge.evaluation.load_grounding_config")
    @patch("predictive_maintenance.knowledge.evaluation.sha256_file")
    @patch("predictive_maintenance.knowledge.evaluation.resolve_retrieval_paths")
    @patch("predictive_maintenance.knowledge.evaluation.load_index")
    def test_frozen_artifact_identity_is_enforced(
        self, mock_load_index, mock_paths, mock_sha, mock_grounding
    ):
        index = self.root / "index.joblib"
        chunks = self.root / "chunks.jsonl"
        mock_load_index.return_value = (
            {"corpus_id": "controlled_corpus", "retrieval_id": "controlled_retrieval"},
            {"index_signature": "sig", "config_fingerprint": "cfg"},
        )
        mock_paths.return_value = type(
            "Paths", (), {"index": index, "chunks": chunks}
        )()
        mock_sha.side_effect = ["b" * 64, "a" * 64]
        mock_grounding.return_value = {"grounding_id": "controlled_grounding"}
        identity = validate_frozen_artifacts(
            self.base_config,
            retrieval_config_path=self.retrieval_config_path,
            grounding_config_path=self.grounding_config_path,
            project_root=self.root,
        )
        self.assertFalse(identity["retrieval_index_modified"])
        self.assertEqual(identity["chunk_sha256"], "a" * 64)

    @patch("predictive_maintenance.knowledge.evaluation.load_grounding_config")
    @patch("predictive_maintenance.knowledge.evaluation.sha256_file")
    @patch("predictive_maintenance.knowledge.evaluation.resolve_retrieval_paths")
    @patch("predictive_maintenance.knowledge.evaluation.load_index")
    def test_frozen_artifact_mismatch_stops_evaluation(
        self, mock_load_index, mock_paths, mock_sha, mock_grounding
    ):
        mock_load_index.return_value = (
            {"corpus_id": "controlled_corpus", "retrieval_id": "controlled_retrieval"},
            {"index_signature": "sig", "config_fingerprint": "cfg"},
        )
        mock_paths.return_value = type(
            "Paths",
            (),
            {"index": self.root / "index", "chunks": self.root / "chunks"},
        )()
        mock_sha.side_effect = ["c" * 64, "a" * 64]
        mock_grounding.return_value = {"grounding_id": "controlled_grounding"}
        with self.assertRaisesRegex(EvaluationError, "identity mismatch"):
            validate_frozen_artifacts(
                self.base_config,
                retrieval_config_path=self.retrieval_config_path,
                grounding_config_path=self.grounding_config_path,
                project_root=self.root,
            )

    @patch("predictive_maintenance.knowledge.evaluation.assemble_answer")
    @patch("predictive_maintenance.knowledge.evaluation.rerank")
    @patch("predictive_maintenance.knowledge.evaluation.retrieve")
    @patch("predictive_maintenance.knowledge.evaluation.load_grounding_config")
    @patch("predictive_maintenance.knowledge.evaluation.validate_frozen_artifacts")
    def test_run_evaluation_writes_atomic_report(
        self,
        mock_identity,
        mock_grounding,
        mock_retrieve,
        mock_rerank,
        mock_assemble,
    ):
        candidate = self._candidate()
        mock_identity.return_value = {"retrieval_index_modified": False}
        mock_grounding.return_value = {"grounding_id": "controlled_grounding"}
        mock_retrieve.return_value = [candidate]
        mock_rerank.return_value = [candidate]

        def answer_for(query, reranked, config):
            if "manufacturer-specified" in query:
                return self._refusal()
            return self._answer(candidate)

        mock_assemble.side_effect = answer_for
        report = run_evaluation(
            self.config_path,
            retrieval_config_path=self.retrieval_config_path,
            grounding_config_path=self.grounding_config_path,
            project_root=self.root,
        )
        report_path = self.root / "outputs" / "knowledge_evaluation_report.json"
        self.assertTrue(report_path.is_file())
        self.assertFalse(
            (self.root / "outputs" / "knowledge_evaluation_report.json.part").exists()
        )
        self.assertEqual(report["status"], "completed")

    @patch("predictive_maintenance.knowledge.evaluation.validate_frozen_artifacts")
    def test_failed_run_invalidates_stale_report(self, mock_identity):
        stale = self.root / "outputs" / "knowledge_evaluation_report.json"
        stale.write_text('{"status":"stale"}\n', encoding="utf-8")
        mock_identity.side_effect = EvaluationError("controlled failure")
        with self.assertRaisesRegex(EvaluationError, "controlled failure"):
            run_evaluation(
                self.config_path,
                retrieval_config_path=self.retrieval_config_path,
                grounding_config_path=self.grounding_config_path,
                project_root=self.root,
            )
        self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()

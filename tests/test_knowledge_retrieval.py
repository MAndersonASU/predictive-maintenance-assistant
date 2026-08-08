"""Controlled tests for deterministic keyword/vector/hybrid retrieval."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.knowledge.retrieval import (
    PRESERVED_RESULT_FIELDS,
    _json_for_cli,
    RetrievalError,
    build_index,
    load_config,
    retrieve,
    sha256_text,
    validate_config,
)


class KnowledgeRetrievalTests(unittest.TestCase):
    """Verify retrieval governance with a small fully local corpus."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        (self.root / "config").mkdir(parents=True)
        (self.root / "data" / "interim" / "knowledge").mkdir(parents=True)
        (self.root / "outputs").mkdir(parents=True)
        self.chunk_path = self.root / "data" / "interim" / "knowledge" / "chunks.jsonl"
        self.index_path = (
            self.root / "data" / "interim" / "knowledge" / "retrieval" / "hybrid_index.joblib"
        )
        self.report_path = self.root / "outputs" / "knowledge_retrieval_report.json"
        self.config_path = self.root / "config" / "knowledge_retrieval.json"

        texts = [
            "Compressor pressure maintenance includes checking leaks filters and pressure drop across the system.",
            "MetroPT records pressure temperature motor current and digital operating signals for predictive maintenance.",
            "Compressed air systems should minimize artificial demand and inappropriate end uses to improve efficiency.",
            "A railway air production unit supplies compressed air used by onboard pneumatic systems and monitored sensors.",
            "Lubrication inspection and preventive maintenance can reduce compressor wear and unexpected downtime.",
            "Dataset provenance requires source identity checksums locators and clear separation of general guidance.",
        ]
        chunks = []
        for index, text in enumerate(texts, start=1):
            chunks.append(self._chunk(index, text))
        self._write_chunks(chunks)
        corpus_sha = self._sha256_file(self.chunk_path)
        self.base_config = {
            "schema_version": 1,
            "retrieval_id": "controlled_retrieval",
            "corpus_id": "controlled_corpus",
            "input_chunk_path": "data/interim/knowledge/chunks.jsonl",
            "index_path": "data/interim/knowledge/retrieval/hybrid_index.joblib",
            "report_path": "outputs/knowledge_retrieval_report.json",
            "reproducibility": {
                "expected_chunk_count": len(chunks),
                "expected_chunk_sha256": corpus_sha,
            },
            "keyword": {
                "lowercase": True,
                "ngram_min": 1,
                "ngram_max": 2,
                "min_df": 1,
                "max_features": 1000,
                "sublinear_tf": True,
            },
            "embedding": {
                "method": "lsa_tfidf",
                "dimension": 3,
                "algorithm": "randomized",
                "n_iter": 7,
                "random_state": 42,
            },
            "hybrid": {
                "vector_weight": 0.65,
                "keyword_weight": 0.35,
                "candidate_k": 6,
                "default_top_k": 3,
                "maximum_top_k": 5,
            },
        }
        self._write_config(self.base_config)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _chunk(self, index: int, text: str) -> dict:
        return {
            "chunk_id": f"source::{index:04d}",
            "source_id": "controlled_source",
            "source_title": "Controlled Compressor Reference",
            "publisher": "Controlled Publisher",
            "source_url": "https://example.invalid/reference",
            "doi": "",
            "classification": "authoritative_general_reference",
            "equipment_relevance": "General compressed-air guidance only.",
            "license_or_usage_status": "Controlled test fixture.",
            "retrieval_identity": "controlled-test-reference",
            "scope_note": "Not exact MetroPT equipment guidance.",
            "source_sha256": "a" * 64,
            "locator": f"page:{index}",
            "unit_index": index,
            "unit_chunk_index": 1,
            "source_chunk_index": index,
            "word_count": len(text.split()),
            "text_sha256": sha256_text(text),
            "text": text,
        }

    def _write_chunks(self, chunks: list[dict]) -> None:
        with self.chunk_path.open("w", encoding="utf-8", newline="\n") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk, sort_keys=True) + "\n")

    def _write_config(self, config: dict) -> None:
        self.config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _sha256_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_valid_config_loads(self) -> None:
        config = load_config(self.config_path)
        self.assertEqual(config["retrieval_id"], "controlled_retrieval")

    def test_hybrid_weights_must_sum_to_one(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["hybrid"]["vector_weight"] = 0.8
        with self.assertRaisesRegex(RetrievalError, "weights must sum"):
            validate_config(config)

    def test_candidate_k_must_cover_maximum_top_k(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["hybrid"]["candidate_k"] = 2
        with self.assertRaisesRegex(RetrievalError, "candidate_k"):
            validate_config(config)

    def test_absolute_output_path_is_rejected(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["index_path"] = str(Path(self.temp.name).resolve() / "outside.joblib")
        with self.assertRaisesRegex(RetrievalError, "project-relative"):
            validate_config(config)

    def test_wrong_corpus_checksum_blocks_build(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["reproducibility"]["expected_chunk_sha256"] = "0" * 64
        self._write_config(config)
        with self.assertRaisesRegex(RetrievalError, "checksum mismatch"):
            build_index(self.config_path, project_root=self.root)

    def test_wrong_chunk_count_blocks_build(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["reproducibility"]["expected_chunk_count"] += 1
        self._write_config(config)
        with self.assertRaisesRegex(RetrievalError, "chunk count mismatch"):
            build_index(self.config_path, project_root=self.root)

    def test_bad_text_checksum_blocks_build(self) -> None:
        lines = [json.loads(line) for line in self.chunk_path.read_text(encoding="utf-8").splitlines()]
        lines[0]["text_sha256"] = "0" * 64
        self._write_chunks(lines)
        config = copy.deepcopy(self.base_config)
        config["reproducibility"]["expected_chunk_sha256"] = self._sha256_file(self.chunk_path)
        self._write_config(config)
        with self.assertRaisesRegex(RetrievalError, "text checksum"):
            build_index(self.config_path, project_root=self.root)

    def test_build_report_records_scope_boundaries(self) -> None:
        report = build_index(self.config_path, project_root=self.root)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["scope"]["reranking_implemented"])
        self.assertFalse(report["scope"]["answer_generation_implemented"])
        self.assertTrue(self.index_path.is_file())
        self.assertTrue(self.report_path.is_file())

    def test_build_is_deterministic_for_same_inputs(self) -> None:
        first = build_index(self.config_path, project_root=self.root)
        second = build_index(self.config_path, project_root=self.root)
        self.assertEqual(first["index_signature"], second["index_signature"])
        self.assertEqual(
            first["embedding"]["document_embeddings_sha256"],
            second["embedding"]["document_embeddings_sha256"],
        )

    def test_retrieval_returns_relevant_compressor_maintenance_chunk(self) -> None:
        build_index(self.config_path, project_root=self.root)
        results = retrieve(
            "compressor pressure maintenance leaks",
            top_k=3,
            config_path=self.config_path,
            project_root=self.root,
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["chunk_id"], "source::0001")

    def test_result_preserves_provenance_and_locator_fields(self) -> None:
        build_index(self.config_path, project_root=self.root)
        result = retrieve(
            "dataset provenance source checksums",
            top_k=1,
            config_path=self.config_path,
            project_root=self.root,
        )[0]
        for field in PRESERVED_RESULT_FIELDS:
            self.assertIn(field, result)
        self.assertEqual(result["locator"], "page:6")
        self.assertEqual(result["classification"], "authoritative_general_reference")

    def test_scores_and_rank_are_exposed_without_rerank_fields(self) -> None:
        build_index(self.config_path, project_root=self.root)
        result = retrieve(
            "compressed air efficiency demand",
            top_k=1,
            config_path=self.config_path,
            project_root=self.root,
        )[0]
        self.assertIn("keyword_score", result)
        self.assertIn("vector_score", result)
        self.assertIn("hybrid_score", result)
        self.assertEqual(result["rank"], 1)
        self.assertNotIn("rerank_score", result)
        self.assertNotIn("answer", result)

    def test_top_k_is_bounded(self) -> None:
        build_index(self.config_path, project_root=self.root)
        with self.assertRaisesRegex(RetrievalError, "exceeds configured"):
            retrieve(
                "compressor",
                top_k=6,
                config_path=self.config_path,
                project_root=self.root,
            )

    def test_unknown_vocabulary_query_returns_no_results(self) -> None:
        build_index(self.config_path, project_root=self.root)
        results = retrieve(
            "zzzxxyyqqq",
            config_path=self.config_path,
            project_root=self.root,
        )
        self.assertEqual(results, [])

    def test_cli_json_is_ascii_safe_and_round_trips_unicode(self) -> None:
        payload = [{"text": "Pressure difference \u2206 remains governed evidence."}]
        serialized = _json_for_cli(payload)
        serialized.encode("ascii")
        self.assertEqual(json.loads(serialized), payload)

    def test_changed_config_invalidates_existing_index(self) -> None:
        build_index(self.config_path, project_root=self.root)
        config = copy.deepcopy(self.base_config)
        config["hybrid"]["vector_weight"] = 0.60
        config["hybrid"]["keyword_weight"] = 0.40
        self._write_config(config)
        with self.assertRaisesRegex(RetrievalError, "different configuration"):
            retrieve(
                "compressor maintenance",
                config_path=self.config_path,
                project_root=self.root,
            )


if __name__ == "__main__":
    unittest.main()

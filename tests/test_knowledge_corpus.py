"""Controlled tests for governed document extraction and chunking."""

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

from predictive_maintenance.knowledge.corpus import (
    CorpusError,
    ExtractedUnit,
    build_chunks_for_source,
    chunk_unit_text,
    extract_html_units,
    extract_source_units,
    extract_txt_units,
    invalidate_generated_corpus_evidence,
    load_corpus_config,
    materialize_source,
    normalize_text,
    resolve_source_path,
    run_corpus_workflow,
    sha256_file,
    sha256_text,
    validate_chunk_records,
    validate_corpus_config,
    validate_extracted_source,
    write_chunks_jsonl,
)


class KnowledgeCorpusTests(unittest.TestCase):
    """Verify corpus governance without relying on live network access."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.temp_dir = Path(self.temporary_directory.name)
        self.project_root = self.temp_dir / "project"
        self.project_root.mkdir()
        self.config_dir = self.project_root / "config"
        self.config_dir.mkdir()
        self.raw_dir = self.project_root / "data" / "raw" / "knowledge"
        self.raw_dir.mkdir(parents=True)
        self.source_path = self.raw_dir / "source.txt"
        self.source_path.write_text(
            "Alpha beta gamma delta epsilon zeta eta theta iota kappa "
            "lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega.\n\n"
            "Second paragraph with compressor maintenance evidence and source provenance.",
            encoding="utf-8",
        )
        self.base_source = {
            "source_id": "controlled_source",
            "title": "Controlled Source",
            "publisher": "Controlled Publisher",
            "source_url": "https://example.invalid/source",
            "doi": "",
            "retrieval_identity": "controlled-test-identity",
            "scope_note": "Controlled source scope note.",
            "license_or_usage_status": "controlled test fixture",
            "equipment_relevance": "General test evidence only.",
            "classification": "authoritative_general_reference",
            "format": "txt",
            "acquisition": "existing_local",
            "local_path": "data/raw/knowledge/source.txt",
            "minimum_extracted_words": 10,
            "required_text_markers": ["compressor", "provenance"],
        }
        self.base_config = {
            "schema_version": 1,
            "corpus_id": "controlled_corpus",
            "description": "Controlled test corpus",
            "chunking": {
                "max_words": 12,
                "overlap_words": 3,
                "minimum_words": 4,
            },
            "sources": [self.base_source],
        }
        self.config_path = self.config_dir / "knowledge_corpus.json"
        self._write_config(self.base_config)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write_config(self, config: dict) -> None:
        self.config_path.write_text(
            json.dumps(config, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_valid_config_loads(self) -> None:
        config = load_corpus_config(self.config_path)
        self.assertEqual(config["corpus_id"], "controlled_corpus")
        self.assertEqual(len(config["sources"]), 1)

    def test_duplicate_source_id_is_rejected(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["sources"].append(copy.deepcopy(self.base_source))
        with self.assertRaisesRegex(CorpusError, "Duplicate source_id"):
            validate_corpus_config(config)

    def test_unknown_classification_is_rejected(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["sources"][0]["classification"] = "exact_equipment_manual"
        with self.assertRaisesRegex(CorpusError, "Unsupported classification"):
            validate_corpus_config(config)

    def test_missing_minimum_content_rule_is_rejected(self) -> None:
        config = copy.deepcopy(self.base_config)
        del config["sources"][0]["minimum_extracted_words"]
        with self.assertRaisesRegex(CorpusError, "missing required field"):
            validate_corpus_config(config)

    def test_required_markers_must_be_non_empty_list(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["sources"][0]["required_text_markers"] = []
        with self.assertRaisesRegex(CorpusError, "required_text_markers"):
            validate_corpus_config(config)

    def test_extracted_content_rejects_short_landing_page(self) -> None:
        source = copy.deepcopy(self.base_source)
        source["minimum_extracted_words"] = 50
        units = [ExtractedUnit(1, "document", "MetroPT landing page only")]
        with self.assertRaisesRegex(CorpusError, "too short"):
            validate_extracted_source(source, units)

    def test_extracted_content_rejects_missing_required_marker(self) -> None:
        source = copy.deepcopy(self.base_source)
        source["minimum_extracted_words"] = 3
        source["required_text_markers"] = ["technical validation"]
        units = [ExtractedUnit(1, "document", "enough words but wrong content") ]
        with self.assertRaisesRegex(CorpusError, "missing required marker"):
            validate_extracted_source(source, units)

    def test_extracted_content_validation_passes_substantive_source(self) -> None:
        units = extract_txt_units(self.source_path)
        result = validate_extracted_source(self.base_source, units)
        self.assertEqual(result["status"], "passed")
        self.assertGreaterEqual(result["extracted_word_count"], 10)


    def test_stable_marker_rule_accepts_verified_pdf_style_text(self) -> None:
        source = copy.deepcopy(self.base_source)
        source["minimum_extracted_words"] = 5
        source["required_text_markers"] = ["MetroPT"]
        units = [
            ExtractedUnit(
                1,
                "page:1",
                "MetroPT sensor description TP2 TP3 compressor pressure data",
            )
        ]
        result = validate_extracted_source(source, units)
        self.assertEqual(result["status"], "passed")

    def test_invalidation_removes_stale_generated_evidence_only(self) -> None:
        interim = self.project_root / "data" / "interim" / "knowledge"
        normalized = interim / "normalized"
        normalized.mkdir(parents=True)
        chunks = interim / "chunks.jsonl"
        chunks.write_text("stale chunk\n", encoding="utf-8")
        (normalized / "source.txt").write_text("stale normalized\n", encoding="utf-8")
        report = self.project_root / "outputs" / "knowledge_corpus_report.json"
        report.parent.mkdir(parents=True)
        report.write_text('{"provenance_validation":"passed"}\n', encoding="utf-8")
        raw_before = self.source_path.read_bytes()

        invalidate_generated_corpus_evidence(
            interim_dir=interim,
            report_path=report,
        )

        self.assertFalse(interim.exists())
        self.assertFalse(report.exists())
        self.assertEqual(self.source_path.read_bytes(), raw_before)

    def test_failed_workflow_does_not_leave_stale_success_report(self) -> None:
        interim = self.project_root / "data" / "interim" / "knowledge"
        report = self.project_root / "outputs" / "knowledge_corpus_report.json"
        interim.mkdir(parents=True)
        (interim / "chunks.jsonl").write_text("old chunks\n", encoding="utf-8")
        report.parent.mkdir(parents=True)
        report.write_text('{"provenance_validation":"passed"}\n', encoding="utf-8")

        bad = copy.deepcopy(self.base_config)
        bad["sources"][0]["required_text_markers"] = ["marker-that-is-not-present"]
        bad_path = self.config_dir / "bad.json"
        bad_path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(CorpusError, "missing required marker"):
            run_corpus_workflow(
                bad_path,
                project_root=self.project_root,
                interim_dir=interim,
                report_path=report,
                offline=True,
            )

        self.assertFalse(report.exists())
        self.assertFalse((interim / "chunks.jsonl").exists())

    def test_overlap_must_be_smaller_than_max_words(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["chunking"]["overlap_words"] = 12
        with self.assertRaisesRegex(CorpusError, "smaller than max_words"):
            validate_corpus_config(config)

    def test_project_relative_path_cannot_escape_root(self) -> None:
        config = copy.deepcopy(self.base_config)
        config["sources"][0]["local_path"] = "../outside.txt"
        with self.assertRaisesRegex(CorpusError, "cannot escape"):
            validate_corpus_config(config)

    def test_normalization_collapses_spacing_and_preserves_paragraphs(self) -> None:
        text = "  A\u00a0  B\r\nC  \r\n\r\n  D   E  "
        self.assertEqual(normalize_text(text), "A B C\n\nD E")

    def test_text_checksum_is_stable(self) -> None:
        self.assertEqual(sha256_text("same"), sha256_text("same"))
        self.assertNotEqual(sha256_text("same"), sha256_text("different"))

    def test_file_checksum_rejects_empty_input(self) -> None:
        empty = self.temp_dir / "empty.txt"
        empty.touch()
        with self.assertRaisesRegex(CorpusError, "empty"):
            sha256_file(empty)

    def test_resolve_source_path_stays_under_project(self) -> None:
        resolved = resolve_source_path(self.base_source, self.project_root)
        self.assertEqual(resolved, self.source_path.resolve())

    def test_existing_local_source_is_not_modified(self) -> None:
        checksum_before = sha256_file(self.source_path)
        resolved = materialize_source(
            self.base_source,
            project_root=self.project_root,
            offline=True,
        )
        checksum_after = sha256_file(resolved)
        self.assertEqual(checksum_before, checksum_after)

    def test_missing_existing_source_raises_actionable_error(self) -> None:
        source = copy.deepcopy(self.base_source)
        source["local_path"] = "data/raw/knowledge/missing.txt"
        with self.assertRaisesRegex(CorpusError, "Required existing source is missing"):
            materialize_source(
                source,
                project_root=self.project_root,
                offline=True,
            )

    def test_offline_remote_source_requires_local_copy(self) -> None:
        source = copy.deepcopy(self.base_source)
        source["acquisition"] = "remote"
        source["local_path"] = "data/raw/knowledge/not_downloaded.txt"
        with self.assertRaisesRegex(CorpusError, "offline mode"):
            materialize_source(
                source,
                project_root=self.project_root,
                offline=True,
            )

    def test_html_extraction_excludes_script_and_style(self) -> None:
        html_path = self.temp_dir / "sample.html"
        html_path.write_text(
            "<html><style>secret-style</style><body><h1>Title</h1>"
            "<script>secret-script</script><p>Visible evidence.</p></body></html>",
            encoding="utf-8",
        )
        units = extract_html_units(html_path)
        self.assertEqual(len(units), 1)
        self.assertIn("Title", units[0].text)
        self.assertIn("Visible evidence.", units[0].text)
        self.assertNotIn("secret-script", units[0].text)
        self.assertNotIn("secret-style", units[0].text)

    def test_text_extraction_returns_normalized_unit(self) -> None:
        units = extract_txt_units(self.source_path)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].locator, "document")
        self.assertIn("Second paragraph", units[0].text)

    def test_unsupported_extraction_format_is_rejected(self) -> None:
        with self.assertRaisesRegex(CorpusError, "Unsupported source format"):
            extract_source_units(self.source_path, "docx")

    def test_chunking_is_deterministic(self) -> None:
        text = " ".join(f"w{i}" for i in range(30))
        first = chunk_unit_text(
            text,
            max_words=10,
            overlap_words=2,
            minimum_words=3,
        )
        second = chunk_unit_text(
            text,
            max_words=10,
            overlap_words=2,
            minimum_words=3,
        )
        self.assertEqual(first, second)

    def test_chunking_preserves_configured_overlap(self) -> None:
        text = " ".join(f"w{i}" for i in range(25))
        chunks = chunk_unit_text(
            text,
            max_words=10,
            overlap_words=2,
            minimum_words=3,
        )
        first_words = chunks[0].split()
        second_words = chunks[1].split()
        self.assertEqual(first_words[-2:], second_words[:2])

    def test_short_text_produces_one_chunk(self) -> None:
        chunks = chunk_unit_text(
            "one two three",
            max_words=10,
            overlap_words=2,
            minimum_words=2,
        )
        self.assertEqual(chunks, ["one two three"])

    def test_chunk_ids_change_when_text_changes(self) -> None:
        checksum = sha256_file(self.source_path)
        first = build_chunks_for_source(
            self.base_source,
            checksum,
            [ExtractedUnit(1, "document", "one two three four five six")],
            {"max_words": 20, "overlap_words": 2, "minimum_words": 2},
        )[0]
        second = build_chunks_for_source(
            self.base_source,
            checksum,
            [ExtractedUnit(1, "document", "one two three four five changed")],
            {"max_words": 20, "overlap_words": 2, "minimum_words": 2},
        )[0]
        self.assertNotEqual(first["chunk_id"], second["chunk_id"])

    def test_chunk_records_preserve_governance_metadata(self) -> None:
        checksum = sha256_file(self.source_path)
        chunks = build_chunks_for_source(
            self.base_source,
            checksum,
            extract_txt_units(self.source_path),
            self.base_config["chunking"],
        )
        first = chunks[0]
        self.assertEqual(first["source_id"], "controlled_source")
        self.assertEqual(
            first["classification"],
            "authoritative_general_reference",
        )
        self.assertEqual(first["source_sha256"], checksum)
        self.assertEqual(first["scope_note"], "Controlled source scope note.")
        validate_chunk_records(chunks)

    def test_duplicate_chunk_id_is_rejected(self) -> None:
        checksum = sha256_file(self.source_path)
        chunks = build_chunks_for_source(
            self.base_source,
            checksum,
            extract_txt_units(self.source_path),
            self.base_config["chunking"],
        )
        duplicated = [chunks[0], copy.deepcopy(chunks[0])]
        with self.assertRaisesRegex(CorpusError, "Duplicate chunk_id"):
            validate_chunk_records(duplicated)

    def test_tampered_chunk_text_is_rejected(self) -> None:
        checksum = sha256_file(self.source_path)
        chunks = build_chunks_for_source(
            self.base_source,
            checksum,
            extract_txt_units(self.source_path),
            self.base_config["chunking"],
        )
        chunks[0]["text"] += " tampered"
        with self.assertRaisesRegex(CorpusError, "checksum mismatch"):
            validate_chunk_records(chunks)

    def test_jsonl_writer_is_byte_deterministic(self) -> None:
        checksum = sha256_file(self.source_path)
        chunks = build_chunks_for_source(
            self.base_source,
            checksum,
            extract_txt_units(self.source_path),
            self.base_config["chunking"],
        )
        first_path = self.temp_dir / "first.jsonl"
        second_path = self.temp_dir / "second.jsonl"
        write_chunks_jsonl(chunks, first_path)
        write_chunks_jsonl(chunks, second_path)
        self.assertEqual(first_path.read_bytes(), second_path.read_bytes())

    def test_workflow_generates_governed_ignored_artifacts(self) -> None:
        interim = self.project_root / "data" / "interim" / "knowledge"
        report_path = self.project_root / "outputs" / "knowledge_corpus_report.json"
        report = run_corpus_workflow(
            self.config_path,
            project_root=self.project_root,
            interim_dir=interim,
            report_path=report_path,
            offline=True,
        )
        self.assertEqual(report["source_count"], 1)
        self.assertGreater(report["chunk_count"], 0)
        self.assertEqual(report["provenance_validation"], "passed")
        self.assertEqual(report["sources"][0]["content_validation"], "passed")
        self.assertGreaterEqual(report["sources"][0]["extracted_word_count"], 10)
        self.assertTrue((interim / "chunks.jsonl").exists())
        self.assertTrue(
            (interim / "normalized" / "controlled_source.txt").exists()
        )
        self.assertTrue(report_path.exists())

    def test_workflow_is_repeatable_for_identical_inputs(self) -> None:
        interim = self.project_root / "data" / "interim" / "knowledge"
        report_path = self.project_root / "outputs" / "knowledge_corpus_report.json"
        first = run_corpus_workflow(
            self.config_path,
            project_root=self.project_root,
            interim_dir=interim,
            report_path=report_path,
            offline=True,
        )
        first_report_bytes = report_path.read_bytes()
        first_chunks_bytes = (interim / "chunks.jsonl").read_bytes()
        second = run_corpus_workflow(
            self.config_path,
            project_root=self.project_root,
            interim_dir=interim,
            report_path=report_path,
            offline=True,
        )
        self.assertEqual(first["chunks_sha256"], second["chunks_sha256"])
        self.assertEqual(first_report_bytes, report_path.read_bytes())
        self.assertEqual(first_chunks_bytes, (interim / "chunks.jsonl").read_bytes())


if __name__ == "__main__":
    unittest.main()

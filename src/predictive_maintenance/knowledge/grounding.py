"""Deterministic reranking, evidence assembly, and citation-grounded answers.

This module extends the governed hybrid retrieval layer without changing or
rebuilding its index. It reranks bounded retrieval candidates, preserves source
classification and provenance, assembles evidence with stable citation IDs,
and refuses equipment-specific answers when exact equipment evidence is absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from predictive_maintenance.knowledge.retrieval import (
    DEFAULT_CONFIG_PATH as DEFAULT_RETRIEVAL_CONFIG_PATH,
    PROJECT_ROOT,
    RetrievalError,
    _json_for_cli,
    retrieve,
)

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "knowledge_grounding.json"
GROUNDING_SCHEMA_VERSION = 1

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
    "what", "when", "where", "which", "with",
}


class GroundingError(RuntimeError):
    """Raised when grounding configuration or evidence controls fail."""


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_int(value: Any, label: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise GroundingError(f"{label} must be an integer >= {minimum}")
    return value


def _require_weight(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise GroundingError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise GroundingError(f"{label} must be finite and between 0 and 1")
    return number


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise GroundingError(f"{label} must be a non-empty list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise GroundingError(f"{label} entries must be non-empty strings")
        normalized.append(item.strip().lower())
    return normalized


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the bounded grounding contract."""
    if config.get("schema_version") != GROUNDING_SCHEMA_VERSION:
        raise GroundingError("schema_version must equal 1")
    for field in ("grounding_id", "report_path"):
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise GroundingError(f"{field} must be a non-empty string")
    report_path = Path(config["report_path"])
    if report_path.is_absolute() or ".." in report_path.parts:
        raise GroundingError("report_path must stay project-relative")

    retrieval = config.get("retrieval")
    if not isinstance(retrieval, dict):
        raise GroundingError("retrieval must be an object")
    _require_int(retrieval.get("candidate_k"), "retrieval.candidate_k")

    reranking = config.get("reranking")
    if not isinstance(reranking, dict):
        raise GroundingError("reranking must be an object")
    weights = [
        _require_weight(reranking.get("hybrid_weight"), "reranking.hybrid_weight"),
        _require_weight(reranking.get("coverage_weight"), "reranking.coverage_weight"),
        _require_weight(reranking.get("phrase_weight"), "reranking.phrase_weight"),
        _require_weight(reranking.get("classification_weight"), "reranking.classification_weight"),
    ]
    if not math.isclose(sum(weights), 1.0, abs_tol=1e-12):
        raise GroundingError("reranking weights must sum to 1.0")
    minimum_score = _require_weight(
        reranking.get("minimum_rerank_score"), "reranking.minimum_rerank_score"
    )
    if minimum_score <= 0.0:
        raise GroundingError("reranking.minimum_rerank_score must be greater than 0")
    _require_int(reranking.get("max_evidence_chunks"), "reranking.max_evidence_chunks")

    answer = config.get("answer")
    if not isinstance(answer, dict):
        raise GroundingError("answer must be an object")
    _require_int(answer.get("max_sentences_per_chunk"), "answer.max_sentences_per_chunk")
    _require_int(answer.get("max_total_sentences"), "answer.max_total_sentences")
    _require_int(answer.get("minimum_evidence_chunks"), "answer.minimum_evidence_chunks")
    prefix = answer.get("citation_prefix")
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*", prefix):
        raise GroundingError("answer.citation_prefix must be uppercase alphanumeric")
    for field in (
        "exact_equipment_classification",
        "exact_dataset_classification",
        "general_classification",
        "insufficient_evidence_message",
    ):
        value = answer.get(field)
        if not isinstance(value, str) or not value.strip():
            raise GroundingError(f"answer.{field} must be a non-empty string")
    _require_string_list(answer.get("equipment_specific_markers"), "answer.equipment_specific_markers")
    _require_string_list(answer.get("dataset_specific_markers"), "answer.dataset_specific_markers")
    return config


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load and validate the grounding configuration."""
    path = Path(path)
    if not path.is_file():
        raise GroundingError(f"Grounding config does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GroundingError(f"Unable to read grounding config: {path}") from error
    if not isinstance(value, dict):
        raise GroundingError("Grounding config root must be an object")
    return validate_config(value)


def _resolve_project_path(project_root: Path, relative: str) -> Path:
    root = Path(project_root).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise GroundingError(f"Configured path escapes project root: {candidate}") from error
    return candidate


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _content_tokens(text: str) -> list[str]:
    return [token for token in _tokens(text) if token not in _STOPWORDS and len(token) > 1]


def detect_intent(query: str, config: dict[str, Any]) -> str:
    """Classify a query only to enforce evidence-scope boundaries."""
    if not isinstance(query, str) or not query.strip():
        raise GroundingError("query must be a non-empty string")
    lowered = " ".join(query.lower().split())
    answer = config["answer"]
    equipment_markers = _require_string_list(
        answer["equipment_specific_markers"], "answer.equipment_specific_markers"
    )
    dataset_markers = _require_string_list(
        answer["dataset_specific_markers"], "answer.dataset_specific_markers"
    )
    if any(marker in lowered for marker in equipment_markers):
        return "equipment_specific"
    if any(marker in lowered for marker in dataset_markers):
        return "dataset_specific"
    return "general"


def _phrase_score(query_tokens: list[str], text_tokens: list[str]) -> float:
    if len(query_tokens) < 2:
        return 0.0
    query_bigrams = set(zip(query_tokens, query_tokens[1:]))
    if not query_bigrams:
        return 0.0
    text_bigrams = set(zip(text_tokens, text_tokens[1:]))
    return len(query_bigrams & text_bigrams) / len(query_bigrams)


def _classification_affinity(classification: str, intent: str, config: dict[str, Any]) -> float:
    answer = config["answer"]
    exact_equipment = answer["exact_equipment_classification"]
    exact_dataset = answer["exact_dataset_classification"]
    general = answer["general_classification"]
    if intent == "equipment_specific":
        if classification == exact_equipment:
            return 1.0
        if classification == exact_dataset:
            return 0.20
        if classification == general:
            return 0.10
        return 0.0
    if intent == "dataset_specific":
        if classification == exact_dataset:
            return 1.0
        if classification == exact_equipment:
            return 0.60
        if classification == general:
            return 0.25
        return 0.0
    if classification == general:
        return 1.0
    if classification in {exact_dataset, exact_equipment}:
        return 0.55
    return 0.0


def _validate_candidate(candidate: dict[str, Any]) -> None:
    required = (
        "rank", "hybrid_score", "chunk_id", "source_id", "source_title", "publisher",
        "source_url", "classification", "scope_note", "locator", "text_sha256", "text",
    )
    missing = [field for field in required if field not in candidate]
    if missing:
        raise GroundingError("Retrieval candidate missing field(s): " + ", ".join(missing))
    if not isinstance(candidate["rank"], int) or isinstance(candidate["rank"], bool):
        raise GroundingError("Retrieval candidate rank must be an integer")
    if not isinstance(candidate["hybrid_score"], (int, float)):
        raise GroundingError("Retrieval candidate hybrid_score must be numeric")
    for field in required[2:]:
        if not isinstance(candidate[field], str):
            raise GroundingError(f"Retrieval candidate field {field} must be a string")


def rerank(query: str, candidates: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Rerank bounded hybrid candidates with deterministic evidence-aware features."""
    validate_config(config)
    if not isinstance(query, str) or not query.strip():
        raise GroundingError("query must be a non-empty string")
    if not isinstance(candidates, list):
        raise GroundingError("candidates must be a list")
    if not candidates:
        return []
    intent = detect_intent(query, config)
    query_tokens = _content_tokens(query)
    query_set = set(query_tokens)
    if not query_set:
        return []
    weights = config["reranking"]
    ranked: list[tuple[float, float, str, dict[str, Any]]] = []
    for candidate in candidates:
        _validate_candidate(candidate)
        text_tokens = _content_tokens(candidate["text"])
        text_set = set(text_tokens)
        coverage = len(query_set & text_set) / len(query_set)
        phrase = _phrase_score(query_tokens, text_tokens)
        affinity = _classification_affinity(candidate["classification"], intent, config)
        hybrid = max(0.0, min(1.0, float(candidate["hybrid_score"])))
        score = (
            weights["hybrid_weight"] * hybrid
            + weights["coverage_weight"] * coverage
            + weights["phrase_weight"] * phrase
            + weights["classification_weight"] * affinity
        )
        enriched = dict(candidate)
        enriched["retrieval_rank"] = candidate["rank"]
        enriched["rerank_score"] = float(score)
        enriched["rerank_components"] = {
            "hybrid": hybrid,
            "query_coverage": float(coverage),
            "phrase": float(phrase),
            "classification_affinity": float(affinity),
        }
        enriched["intent"] = intent
        ranked.append((float(score), hybrid, candidate["chunk_id"], enriched))
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
    output: list[dict[str, Any]] = []
    for new_rank, (_, _, _, candidate) in enumerate(ranked, start=1):
        candidate["rerank_rank"] = new_rank
        output.append(candidate)
    return output


def _citation_record(candidate: dict[str, Any], citation_id: str) -> dict[str, Any]:
    return {
        "citation_id": citation_id,
        "chunk_id": candidate["chunk_id"],
        "source_id": candidate["source_id"],
        "source_title": candidate["source_title"],
        "publisher": candidate["publisher"],
        "source_url": candidate["source_url"],
        "doi": candidate.get("doi", ""),
        "classification": candidate["classification"],
        "equipment_relevance": candidate.get("equipment_relevance", ""),
        "scope_note": candidate["scope_note"],
        "locator": candidate["locator"],
        "source_sha256": candidate.get("source_sha256", ""),
        "text_sha256": candidate["text_sha256"],
    }


def _sentence_candidates(text: str) -> list[str]:
    sentences = [part.strip() for part in _SENTENCE_RE.split(text.strip()) if part.strip()]
    return sentences or ([text.strip()] if text.strip() else [])


def _select_sentences(query: str, candidate: dict[str, Any], maximum: int) -> list[str]:
    query_set = set(_content_tokens(query))
    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(_sentence_candidates(candidate["text"])):
        sentence_set = set(_content_tokens(sentence))
        overlap = len(query_set & sentence_set)
        score = overlap / max(1, len(query_set))
        scored.append((score, index, sentence))
    scored.sort(key=lambda row: (-row[0], row[1]))
    selected = [sentence for score, _, sentence in scored if score > 0.0][:maximum]
    if not selected and scored:
        selected = [scored[0][2]]
    return selected


def assemble_answer(query: str, reranked: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Assemble a bounded answer or a governed insufficient-evidence refusal."""
    validate_config(config)
    intent = detect_intent(query, config)
    reranking_cfg = config["reranking"]
    answer_cfg = config["answer"]
    minimum_score = float(reranking_cfg["minimum_rerank_score"])
    max_chunks = int(reranking_cfg["max_evidence_chunks"])
    selected = [item for item in reranked if float(item["rerank_score"]) >= minimum_score][:max_chunks]

    exact_equipment = answer_cfg["exact_equipment_classification"]
    if intent == "equipment_specific":
        exact = [item for item in selected if item["classification"] == exact_equipment]
        if not exact:
            citations = [
                _citation_record(item, f"{answer_cfg['citation_prefix']}{index}")
                for index, item in enumerate(selected, start=1)
            ]
            return {
                "schema_version": 1,
                "status": "insufficient_evidence",
                "reason_code": "no_exact_equipment_evidence",
                "intent": intent,
                "answer": (
                    answer_cfg["insufficient_evidence_message"]
                    + " The available governed sources may provide dataset context or general "
                    "compressed-air guidance, but they are not verified as the exact equipment manual."
                ),
                "citations": citations,
                "evidence_chunk_count": 0,
                "general_guidance_available": bool(selected),
            }

    if len(selected) < int(answer_cfg["minimum_evidence_chunks"]):
        return {
            "schema_version": 1,
            "status": "insufficient_evidence",
            "reason_code": "below_evidence_threshold",
            "intent": intent,
            "answer": answer_cfg["insufficient_evidence_message"],
            "citations": [],
            "evidence_chunk_count": 0,
            "general_guidance_available": False,
        }

    citations: list[dict[str, Any]] = []
    answer_sentences: list[str] = []
    max_total = int(answer_cfg["max_total_sentences"])
    per_chunk = int(answer_cfg["max_sentences_per_chunk"])
    for index, item in enumerate(selected, start=1):
        citation_id = f"{answer_cfg['citation_prefix']}{index}"
        citations.append(_citation_record(item, citation_id))
        for sentence in _select_sentences(query, item, per_chunk):
            if len(answer_sentences) >= max_total:
                break
            answer_sentences.append(f"{sentence} [{citation_id}]")
        if len(answer_sentences) >= max_total:
            break

    if not answer_sentences:
        return {
            "schema_version": 1,
            "status": "insufficient_evidence",
            "reason_code": "no_supported_sentence",
            "intent": intent,
            "answer": answer_cfg["insufficient_evidence_message"],
            "citations": citations,
            "evidence_chunk_count": 0,
            "general_guidance_available": bool(selected),
        }

    prefix = {
        "general": "Authoritative general guidance: ",
        "dataset_specific": "Governed dataset evidence: ",
        "equipment_specific": "Verified equipment evidence: ",
    }[intent]

    return {
        "schema_version": 1,
        "status": "answered",
        "reason_code": "grounded",
        "intent": intent,
        "answer": prefix + " ".join(answer_sentences),
        "citations": citations,
        "evidence_chunk_count": len(citations),
        "general_guidance_available": any(
            item["classification"] == answer_cfg["general_classification"] for item in selected
        ),
    }


def answer_query(
    query: str,
    *,
    grounding_config_path: Path = DEFAULT_CONFIG_PATH,
    retrieval_config_path: Path = DEFAULT_RETRIEVAL_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Run bounded hybrid retrieval, deterministic reranking, and answer assembly."""
    config = load_config(grounding_config_path)
    candidate_k = config["retrieval"]["candidate_k"]
    try:
        candidates = retrieve(
            query, top_k=candidate_k, config_path=retrieval_config_path, project_root=project_root
        )
    except RetrievalError as error:
        raise GroundingError(f"Governed retrieval failed: {error}") from error
    reranked = rerank(query, candidates, config)
    result = assemble_answer(query, reranked, config)
    result["grounding_id"] = config["grounding_id"]
    result["grounding_config_sha256"] = _canonical_sha256(config)
    result["retrieval_candidate_count"] = len(candidates)
    result["reranked_candidate_count"] = len(reranked)
    result["top_reranked"] = [
        {
            "rerank_rank": item["rerank_rank"],
            "retrieval_rank": item["retrieval_rank"],
            "rerank_score": item["rerank_score"],
            "hybrid_score": item["hybrid_score"],
            "chunk_id": item["chunk_id"],
            "source_id": item["source_id"],
            "classification": item["classification"],
            "locator": item["locator"],
        }
        for item in reranked[: config["reranking"]["max_evidence_chunks"]]
    ]
    return result


def validate_grounding(
    *,
    grounding_config_path: Path = DEFAULT_CONFIG_PATH,
    retrieval_config_path: Path = DEFAULT_RETRIEVAL_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Run three bounded smoke cases and persist a governed grounding report."""
    config = load_config(grounding_config_path)
    cases = [
        {
            "case_id": "dataset_context",
            "query": "What signals are described for the MetroPT predictive-maintenance dataset?",
            "expected_status": "answered",
        },
        {
            "case_id": "general_maintenance",
            "query": "What general compressed-air maintenance guidance addresses leaks and pressure losses?",
            "expected_status": "answered",
        },
        {
            "case_id": "equipment_specific_refusal",
            "query": "What is the manufacturer-specified lubrication interval for the MetroPT compressor?",
            "expected_status": "insufficient_evidence",
        },
    ]
    case_results = []
    for case in cases:
        result = answer_query(
            case["query"],
            grounding_config_path=grounding_config_path,
            retrieval_config_path=retrieval_config_path,
            project_root=project_root,
        )
        case_results.append(
            {
                "case_id": case["case_id"],
                "query": case["query"],
                "expected_status": case["expected_status"],
                "actual_status": result["status"],
                "reason_code": result["reason_code"],
                "intent": result["intent"],
                "citation_count": len(result["citations"]),
                "source_classifications": sorted(
                    {citation["classification"] for citation in result["citations"]}
                ),
                "passed": result["status"] == case["expected_status"],
            }
        )
    status = "passed" if all(case["passed"] for case in case_results) else "failed"
    report = {
        "schema_version": 1,
        "status": status,
        "grounding_id": config["grounding_id"],
        "grounding_config_sha256": _canonical_sha256(config),
        "deterministic_reranking": True,
        "citation_formatting": True,
        "citation_grounded_answer_assembly": True,
        "insufficient_evidence_refusal": True,
        "exact_equipment_boundary_enforced": True,
        "retrieval_index_modified": False,
        "evaluation_scope": (
            "Implementation smoke validation only. Retrieval quality and answer quality are not "
            "formally evaluated here; governed RAG evaluation remains a separate milestone."
        ),
        "cases": case_results,
    }
    report_path = _resolve_project_path(project_root, config["report_path"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return report


def _print_json(value: Any) -> None:
    print(_json_for_cli(value))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--retrieval-config", type=Path, default=DEFAULT_RETRIEVAL_CONFIG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)
    query_parser = subparsers.add_parser("query", help="Return one governed grounded answer.")
    query_parser.add_argument("query")
    subparsers.add_parser(
        "validate", help="Run bounded implementation smoke cases and write the grounding report."
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "query":
        _print_json(
            answer_query(
                args.query,
                grounding_config_path=args.config,
                retrieval_config_path=args.retrieval_config,
            )
        )
        return 0
    if args.command == "validate":
        report = validate_grounding(
            grounding_config_path=args.config,
            retrieval_config_path=args.retrieval_config,
        )
        _print_json(report)
        return 0 if report["status"] == "passed" else 1
    raise GroundingError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

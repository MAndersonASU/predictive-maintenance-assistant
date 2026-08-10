"""Governed retrieval and grounded-answer evaluation.

This module evaluates the already-frozen technical-knowledge pipeline without
rebuilding the corpus, refitting retrieval, changing reranking parameters, or
introducing a model judge. Retrieval quality, citation correctness,
faithfulness, answer usefulness, failure cases, and limitations are reported as
separate dimensions.

The evaluator is descriptive. Low scores remain visible evidence and do not
trigger retuning or convert the report into an unsupported quality claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from predictive_maintenance.knowledge.grounding import (
    DEFAULT_CONFIG_PATH as DEFAULT_GROUNDING_CONFIG_PATH,
    assemble_answer,
    load_config as load_grounding_config,
    rerank,
)
from predictive_maintenance.knowledge.retrieval import (
    DEFAULT_CONFIG_PATH as DEFAULT_RETRIEVAL_CONFIG_PATH,
    PROJECT_ROOT,
    load_index,
    resolve_paths as resolve_retrieval_paths,
    retrieve,
    sha256_file,
)

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "knowledge_evaluation.json"
EVALUATION_SCHEMA_VERSION = 1
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_CITATION_MARKER_RE = re.compile(r"\[([A-Z][A-Z0-9]*)\]")
_ANSWER_PREFIXES = (
    "Authoritative general guidance:",
    "Governed dataset evidence:",
    "Verified equipment evidence:",
)
_ALLOWED_CATEGORIES = {"dataset", "general_guidance", "equipment_boundary"}
_ALLOWED_STATUSES = {"answered", "insufficient_evidence"}


class EvaluationError(RuntimeError):
    """Raised when evaluation governance or execution checks fail."""


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label} must be a non-empty string")
    return value.strip()


def _require_sha256(value: Any, label: str) -> str:
    value = _require_nonempty_string(value, label)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise EvaluationError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _require_string_list(
    value: Any,
    label: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        requirement = "a list" if allow_empty else "a non-empty list"
        raise EvaluationError(f"{label} must be {requirement}")
    result: list[str] = []
    for item in value:
        result.append(_require_nonempty_string(item, f"{label} entry"))
    return result


def _validate_case(case: dict[str, Any], index: int) -> None:
    label = f"cases[{index}]"
    _require_nonempty_string(case.get("case_id"), f"{label}.case_id")
    category = _require_nonempty_string(case.get("category"), f"{label}.category")
    if category not in _ALLOWED_CATEGORIES:
        raise EvaluationError(f"{label}.category is not supported: {category}")
    _require_nonempty_string(case.get("query"), f"{label}.query")

    expected_status = _require_nonempty_string(
        case.get("expected_status"), f"{label}.expected_status"
    )
    if expected_status not in _ALLOWED_STATUSES:
        raise EvaluationError(
            f"{label}.expected_status must be one of {sorted(_ALLOWED_STATUSES)}"
        )
    _require_nonempty_string(
        case.get("expected_reason_code"), f"{label}.expected_reason_code"
    )
    _require_nonempty_string(case.get("expected_intent"), f"{label}.expected_intent")

    relevant = _require_string_list(
        case.get("relevant_source_ids"),
        f"{label}.relevant_source_ids",
        allow_empty=True,
    )
    classifications = _require_string_list(
        case.get("expected_source_classifications"),
        f"{label}.expected_source_classifications",
        allow_empty=True,
    )
    concepts = case.get("required_concepts")
    if not isinstance(concepts, list):
        raise EvaluationError(f"{label}.required_concepts must be a list")
    for concept_index, group in enumerate(concepts):
        _require_string_list(group, f"{label}.required_concepts[{concept_index}]")

    if category == "equipment_boundary":
        if relevant or classifications or concepts:
            raise EvaluationError(
                f"{label} equipment_boundary cases must not assert unavailable "
                "relevant sources, source classifications, or answer concepts"
            )
        if expected_status != "insufficient_evidence":
            raise EvaluationError(
                f"{label} equipment_boundary cases must expect insufficient_evidence"
            )
        if case["expected_reason_code"] != "no_exact_equipment_evidence":
            raise EvaluationError(
                f"{label} equipment_boundary cases must expect no_exact_equipment_evidence"
            )
    else:
        if not relevant:
            raise EvaluationError(f"{label} answerable cases need relevant_source_ids")
        if not classifications:
            raise EvaluationError(
                f"{label} answerable cases need expected_source_classifications"
            )
        if not concepts:
            raise EvaluationError(f"{label} answerable cases need required_concepts")
        if expected_status != "answered":
            raise EvaluationError(f"{label} answerable cases must expect answered")


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the frozen evaluation contract before running any case."""
    if config.get("schema_version") != EVALUATION_SCHEMA_VERSION:
        raise EvaluationError("schema_version must equal 1")
    _require_nonempty_string(config.get("evaluation_id"), "evaluation_id")

    report_path = Path(_require_nonempty_string(config.get("report_path"), "report_path"))
    if report_path.is_absolute() or ".." in report_path.parts:
        raise EvaluationError("report_path must stay project-relative")

    frozen = config.get("frozen_artifacts")
    if not isinstance(frozen, dict):
        raise EvaluationError("frozen_artifacts must be an object")
    for field in ("corpus_id", "retrieval_id", "grounding_id"):
        _require_nonempty_string(frozen.get(field), f"frozen_artifacts.{field}")
    _require_sha256(
        frozen.get("expected_chunk_sha256"),
        "frozen_artifacts.expected_chunk_sha256",
    )
    _require_sha256(
        frozen.get("expected_retrieval_index_sha256"),
        "frozen_artifacts.expected_retrieval_index_sha256",
    )

    retrieval = config.get("retrieval")
    if not isinstance(retrieval, dict):
        raise EvaluationError("retrieval must be an object")
    top_k = retrieval.get("evaluation_top_k")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise EvaluationError("retrieval.evaluation_top_k must be a positive integer")
    cutoffs = retrieval.get("metric_cutoffs")
    if (
        not isinstance(cutoffs, list)
        or not cutoffs
        or any(
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 1
            for value in cutoffs
        )
    ):
        raise EvaluationError(
            "retrieval.metric_cutoffs must be a non-empty list of positive integers"
        )
    if cutoffs != sorted(set(cutoffs)):
        raise EvaluationError("retrieval.metric_cutoffs must be unique and sorted")
    if max(cutoffs) > top_k:
        raise EvaluationError(
            "retrieval.metric_cutoffs cannot exceed retrieval.evaluation_top_k"
        )

    usefulness = config.get("usefulness")
    if not isinstance(usefulness, dict):
        raise EvaluationError("usefulness must be an object")
    minimum = usefulness.get("minimum_concept_coverage")
    if (
        not isinstance(minimum, (int, float))
        or isinstance(minimum, bool)
        or not math.isfinite(float(minimum))
        or float(minimum) < 0.0
        or float(minimum) > 1.0
    ):
        raise EvaluationError(
            "usefulness.minimum_concept_coverage must be finite and between 0 and 1"
        )

    cases = config.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvaluationError("cases must be a non-empty list")
    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise EvaluationError(f"cases[{index}] must be an object")
        _validate_case(case, index)
        case_id = case["case_id"]
        if case_id in seen_ids:
            raise EvaluationError(f"Duplicate case_id: {case_id}")
        seen_ids.add(case_id)

    limitations = _require_string_list(config.get("limitations"), "limitations")
    if len(limitations) < 3:
        raise EvaluationError("limitations must document at least three limitations")
    return config


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load and validate the governed evaluation configuration."""
    path = Path(path)
    if not path.is_file():
        raise EvaluationError(f"Evaluation config does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvaluationError(f"Unable to read evaluation config: {path}") from error
    if not isinstance(value, dict):
        raise EvaluationError("Evaluation config root must be an object")
    return validate_config(value)


def _resolve_project_path(project_root: Path, relative: str, label: str) -> Path:
    root = Path(project_root).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise EvaluationError(f"{label} escapes the project root: {candidate}") from error
    return candidate


def _normalized_text(value: str) -> str:
    return " ".join(value.lower().split())


def _content_tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(value) if len(token) > 1}


def _first_relevant_rank(
    candidates: list[dict[str, Any]],
    relevant_source_ids: list[str],
) -> int | None:
    relevant = set(relevant_source_ids)
    for candidate in candidates:
        if candidate.get("source_id") in relevant:
            rank = candidate.get("rank")
            if isinstance(rank, int) and not isinstance(rank, bool) and rank > 0:
                return rank
    return None


def _classification_at_one(
    candidates: list[dict[str, Any]],
    expected_classifications: list[str],
) -> bool | None:
    if not expected_classifications:
        return None
    if not candidates:
        return False
    return candidates[0].get("classification") in set(expected_classifications)


def _concept_coverage(answer_text: str, concept_groups: list[list[str]]) -> float | None:
    if not concept_groups:
        return None
    normalized = _normalized_text(answer_text)
    covered = 0
    for group in concept_groups:
        if any(_normalized_text(option) in normalized for option in group):
            covered += 1
    return covered / len(concept_groups)


def _candidate_by_chunk(
    reranked: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        item["chunk_id"]: item
        for item in reranked
        if isinstance(item, dict) and isinstance(item.get("chunk_id"), str)
    }


def _citation_traceability(
    citations: list[dict[str, Any]],
    reranked: list[dict[str, Any]],
) -> tuple[int, int]:
    by_chunk = _candidate_by_chunk(reranked)
    fields = ("chunk_id", "source_id", "classification", "locator", "text_sha256")
    traceable = 0
    for citation in citations:
        candidate = by_chunk.get(citation.get("chunk_id"))
        if candidate is None:
            continue
        if all(citation.get(field) == candidate.get(field) for field in fields):
            traceable += 1
    return traceable, len(citations)


def _citation_marker_coverage(
    answer_text: str,
    citations: list[dict[str, Any]],
) -> bool:
    marker_ids = _CITATION_MARKER_RE.findall(answer_text)
    citation_ids = [
        citation.get("citation_id")
        for citation in citations
        if isinstance(citation.get("citation_id"), str)
    ]
    if not citations:
        return not marker_ids
    return (
        bool(marker_ids)
        and set(marker_ids) == set(citation_ids)
        and all(citation_id in marker_ids for citation_id in citation_ids)
    )


def _claims_with_markers(answer_text: str) -> list[tuple[str, str]]:
    claims: list[tuple[str, str]] = []
    previous_end = 0
    for match in _CITATION_MARKER_RE.finditer(answer_text):
        claim = answer_text[previous_end : match.start()].strip()
        for prefix in _ANSWER_PREFIXES:
            if claim.startswith(prefix):
                claim = claim[len(prefix) :].strip()
                break
        if claim:
            claims.append((claim, match.group(1)))
        previous_end = match.end()
    return claims


def _faithfulness_support(
    answer_text: str,
    citations: list[dict[str, Any]],
    reranked: list[dict[str, Any]],
) -> tuple[int, int]:
    citation_to_candidate: dict[str, dict[str, Any]] = {}
    by_chunk = _candidate_by_chunk(reranked)
    for citation in citations:
        citation_id = citation.get("citation_id")
        candidate = by_chunk.get(citation.get("chunk_id"))
        if isinstance(citation_id, str) and candidate is not None:
            citation_to_candidate[citation_id] = candidate

    supported = 0
    claims = _claims_with_markers(answer_text)
    for claim, citation_id in claims:
        candidate = citation_to_candidate.get(citation_id)
        if candidate is None:
            continue
        evidence = candidate.get("text")
        if not isinstance(evidence, str):
            continue
        if _normalized_text(claim) in _normalized_text(evidence):
            supported += 1
    return supported, len(claims)


def evaluate_case(
    case: dict[str, Any],
    candidates: list[dict[str, Any]],
    reranked: list[dict[str, Any]],
    answer: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Score one case without changing retrieval or grounding behavior."""
    _validate_case(case, 0)
    if not isinstance(candidates, list) or not isinstance(reranked, list):
        raise EvaluationError("candidates and reranked must be lists")
    if not isinstance(answer, dict):
        raise EvaluationError("answer must be an object")

    expected_status = case["expected_status"]
    expected_reason = case["expected_reason_code"]
    expected_intent = case["expected_intent"]
    relevant_ids = case["relevant_source_ids"]
    expected_classifications = case["expected_source_classifications"]
    first_rank = _first_relevant_rank(candidates, relevant_ids)
    cutoffs = config["retrieval"]["metric_cutoffs"]

    retrieval_metrics: dict[str, Any] = {
        "first_relevant_source_rank": first_rank,
        "reciprocal_rank": (1.0 / first_rank if first_rank is not None else 0.0)
        if relevant_ids
        else None,
        "top1_expected_classification": _classification_at_one(
            candidates, expected_classifications
        ),
    }
    for cutoff in cutoffs:
        retrieval_metrics[f"source_hit_at_{cutoff}"] = (
            first_rank is not None and first_rank <= cutoff
            if relevant_ids
            else None
        )

    exact_equipment_retrieved = any(
        candidate.get("classification") == "exact_equipment_source"
        for candidate in candidates
    )
    retrieval_metrics["boundary_no_exact_equipment_retrieved"] = (
        not exact_equipment_retrieved
        if case["category"] == "equipment_boundary"
        else None
    )

    citations = answer.get("citations", [])
    if not isinstance(citations, list):
        raise EvaluationError("answer.citations must be a list")
    traceable, citation_count = _citation_traceability(citations, reranked)
    # Answer citation markers are required only when the system claims an answer.
    # An insufficient-evidence refusal may still expose traceable retrieved-source
    # metadata as context; those citations are not presented as support for an
    # equipment-specific claim and therefore require no inline answer markers.
    marker_coverage = (
        _citation_marker_coverage(str(answer.get("answer", "")), citations)
        if answer.get("status") == "answered"
        else None
    )

    aligned = 0
    scoped_citation_count = 0
    if expected_classifications:
        expected_set = set(expected_classifications)
        for citation in citations:
            scoped_citation_count += 1
            if citation.get("classification") in expected_set:
                aligned += 1

    citation_metrics = {
        "citation_count": citation_count,
        "traceable_citation_count": traceable,
        "traceability_rate": traceable / citation_count if citation_count else None,
        "marker_coverage": marker_coverage,
        "source_scope_aligned_citation_count": aligned,
        "source_scope_citation_count": scoped_citation_count,
        "source_scope_alignment_rate": (
            aligned / scoped_citation_count if scoped_citation_count else None
        ),
    }

    supported_claims, claim_count = _faithfulness_support(
        str(answer.get("answer", "")),
        citations,
        reranked,
    )
    refusal_boundary_pass = (
        answer.get("status") == "insufficient_evidence"
        and answer.get("reason_code") == "no_exact_equipment_evidence"
        and answer.get("intent") == "equipment_specific"
    ) if case["category"] == "equipment_boundary" else None

    faithfulness_metrics = {
        "cited_claim_count": claim_count,
        "supported_cited_claim_count": supported_claims,
        "supported_cited_claim_rate": (
            supported_claims / claim_count if claim_count else None
        ),
        "equipment_refusal_boundary_pass": refusal_boundary_pass,
    }

    status_match = answer.get("status") == expected_status
    reason_match = answer.get("reason_code") == expected_reason
    intent_match = answer.get("intent") == expected_intent
    concept_coverage = _concept_coverage(
        str(answer.get("answer", "")),
        case["required_concepts"],
    )
    minimum_concept = float(config["usefulness"]["minimum_concept_coverage"])
    if case["category"] == "equipment_boundary":
        usefulness_pass = bool(status_match and reason_match and intent_match)
    else:
        usefulness_pass = bool(
            status_match
            and reason_match
            and intent_match
            and concept_coverage is not None
            and concept_coverage >= minimum_concept
        )

    usefulness_metrics = {
        "expected_status_match": status_match,
        "expected_reason_match": reason_match,
        "expected_intent_match": intent_match,
        "concept_coverage": concept_coverage,
        "minimum_concept_coverage": minimum_concept
        if concept_coverage is not None
        else None,
        "usefulness_proxy_pass": usefulness_pass,
    }

    failures: list[str] = []
    if relevant_ids:
        largest_cutoff = max(cutoffs)
        if retrieval_metrics[f"source_hit_at_{largest_cutoff}"] is not True:
            failures.append(f"retrieval_source_miss_at_{largest_cutoff}")
        if retrieval_metrics["top1_expected_classification"] is not True:
            failures.append("retrieval_top1_classification_mismatch")
    elif retrieval_metrics["boundary_no_exact_equipment_retrieved"] is not True:
        failures.append("equipment_boundary_retrieved_exact_equipment_source")

    if citations:
        if citation_metrics["traceability_rate"] != 1.0:
            failures.append("citation_traceability_failure")
        if (
            answer.get("status") == "answered"
            and citation_metrics["marker_coverage"] is not True
        ):
            failures.append("citation_marker_coverage_failure")
        if (
            expected_classifications
            and citation_metrics["source_scope_alignment_rate"] != 1.0
        ):
            failures.append("citation_source_scope_misalignment")
    elif expected_status == "answered":
        failures.append("answered_case_without_citation")

    if claim_count and faithfulness_metrics["supported_cited_claim_rate"] != 1.0:
        failures.append("unsupported_cited_claim")
    if case["category"] == "equipment_boundary" and refusal_boundary_pass is not True:
        failures.append("equipment_refusal_boundary_failure")
    if not status_match:
        failures.append("unexpected_answer_status")
    if not reason_match:
        failures.append("unexpected_reason_code")
    if not intent_match:
        failures.append("unexpected_intent")
    if concept_coverage is not None and concept_coverage < minimum_concept:
        failures.append("low_usefulness_concept_coverage")

    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "query": case["query"],
        "expected": {
            "status": expected_status,
            "reason_code": expected_reason,
            "intent": expected_intent,
            "relevant_source_ids": relevant_ids,
            "source_classifications": expected_classifications,
        },
        "observed": {
            "status": answer.get("status"),
            "reason_code": answer.get("reason_code"),
            "intent": answer.get("intent"),
            "retrieval_candidate_count": len(candidates),
            "reranked_candidate_count": len(reranked),
            "citation_count": len(citations),
        },
        "retrieval": retrieval_metrics,
        "citation_correctness": citation_metrics,
        "faithfulness": faithfulness_metrics,
        "answer_usefulness": usefulness_metrics,
        "failure_flags": failures,
    }


def _fraction(values: Iterable[bool]) -> float | None:
    sequence = list(values)
    return sum(1 for value in sequence if value) / len(sequence) if sequence else None


def aggregate_results(
    case_results: list[dict[str, Any]],
    identity: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate dimensions separately and retain per-case failures."""
    if not case_results:
        raise EvaluationError("At least one case result is required")

    labeled = [
        case
        for case in case_results
        if case["expected"]["relevant_source_ids"]
    ]
    boundary = [
        case for case in case_results if case["category"] == "equipment_boundary"
    ]
    answered_expected = [
        case for case in case_results if case["expected"]["status"] == "answered"
    ]

    retrieval_summary: dict[str, Any] = {
        "labeled_source_retrieval_case_count": len(labeled),
        "mean_reciprocal_rank": (
            sum(case["retrieval"]["reciprocal_rank"] for case in labeled) / len(labeled)
            if labeled
            else None
        ),
        "top1_expected_classification_rate": _fraction(
            case["retrieval"]["top1_expected_classification"] for case in labeled
        ),
        "equipment_boundary_case_count": len(boundary),
        "boundary_no_exact_equipment_retrieved_rate": _fraction(
            case["retrieval"]["boundary_no_exact_equipment_retrieved"]
            for case in boundary
        ),
    }
    for cutoff in config["retrieval"]["metric_cutoffs"]:
        retrieval_summary[f"source_hit_at_{cutoff}_rate"] = _fraction(
            case["retrieval"][f"source_hit_at_{cutoff}"] for case in labeled
        )

    citation_total = sum(
        case["citation_correctness"]["citation_count"] for case in case_results
    )
    citation_traceable = sum(
        case["citation_correctness"]["traceable_citation_count"]
        for case in case_results
    )
    scoped_total = sum(
        case["citation_correctness"]["source_scope_citation_count"]
        for case in case_results
    )
    scoped_aligned = sum(
        case["citation_correctness"]["source_scope_aligned_citation_count"]
        for case in case_results
    )
    citation_summary = {
        "citation_count": citation_total,
        "traceable_citation_count": citation_traceable,
        "traceability_rate": (
            citation_traceable / citation_total if citation_total else None
        ),
        "marker_coverage_case_rate": _fraction(
            case["citation_correctness"]["marker_coverage"]
            for case in case_results
            if case["citation_correctness"]["marker_coverage"] is not None
        ),
        "source_scope_alignment_rate": (
            scoped_aligned / scoped_total if scoped_total else None
        ),
    }

    claim_total = sum(
        case["faithfulness"]["cited_claim_count"] for case in case_results
    )
    supported_total = sum(
        case["faithfulness"]["supported_cited_claim_count"]
        for case in case_results
    )
    faithfulness_summary = {
        "cited_claim_count": claim_total,
        "supported_cited_claim_count": supported_total,
        "supported_cited_claim_rate": (
            supported_total / claim_total if claim_total else None
        ),
        "equipment_refusal_boundary_pass_rate": _fraction(
            case["faithfulness"]["equipment_refusal_boundary_pass"]
            for case in boundary
        ),
    }

    concept_values = [
        case["answer_usefulness"]["concept_coverage"]
        for case in answered_expected
        if case["answer_usefulness"]["concept_coverage"] is not None
    ]
    usefulness_summary = {
        "case_count": len(case_results),
        "expected_status_rate": _fraction(
            case["answer_usefulness"]["expected_status_match"]
            for case in case_results
        ),
        "expected_reason_rate": _fraction(
            case["answer_usefulness"]["expected_reason_match"]
            for case in case_results
        ),
        "expected_intent_rate": _fraction(
            case["answer_usefulness"]["expected_intent_match"]
            for case in case_results
        ),
        "mean_concept_coverage_answered_cases": (
            sum(concept_values) / len(concept_values) if concept_values else None
        ),
        "usefulness_proxy_pass_rate": _fraction(
            case["answer_usefulness"]["usefulness_proxy_pass"]
            for case in case_results
        ),
    }

    failure_cases = [
        {
            "case_id": case["case_id"],
            "category": case["category"],
            "failure_flags": case["failure_flags"],
        }
        for case in case_results
        if case["failure_flags"]
    ]

    return {
        "schema_version": 1,
        "status": "completed",
        "evaluation_id": config["evaluation_id"],
        "evaluation_config_sha256": _canonical_sha256(config),
        "quality_claim_policy": (
            "Descriptive governed evaluation only. Metrics and failure cases must "
            "not be converted into unsupported production, safety, or business claims."
        ),
        "frozen_artifact_identity": identity,
        "retrieval_quality": retrieval_summary,
        "citation_correctness": citation_summary,
        "faithfulness": faithfulness_summary,
        "answer_usefulness": usefulness_summary,
        "failure_case_count": len(failure_cases),
        "failure_cases": failure_cases,
        "limitations": list(config["limitations"]),
        "cases": case_results,
    }


def validate_frozen_artifacts(
    config: dict[str, Any],
    *,
    retrieval_config_path: Path = DEFAULT_RETRIEVAL_CONFIG_PATH,
    grounding_config_path: Path = DEFAULT_GROUNDING_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Verify that evaluation is running against the exact frozen RAG artifacts."""
    validate_config(config)
    try:
        retrieval_config, index_payload = load_index(
            retrieval_config_path,
            project_root=project_root,
        )
    except Exception as error:
        raise EvaluationError(f"Unable to validate frozen retrieval index: {error}") from error

    retrieval_paths = resolve_retrieval_paths(retrieval_config, project_root)
    actual_index_sha = sha256_file(retrieval_paths.index)
    actual_chunk_sha = sha256_file(retrieval_paths.chunks)
    grounding_config = load_grounding_config(grounding_config_path)

    frozen = config["frozen_artifacts"]
    checks = {
        "corpus_id": retrieval_config.get("corpus_id"),
        "retrieval_id": retrieval_config.get("retrieval_id"),
        "grounding_id": grounding_config.get("grounding_id"),
        "chunk_sha256": actual_chunk_sha,
        "retrieval_index_sha256": actual_index_sha,
    }
    expected = {
        "corpus_id": frozen["corpus_id"],
        "retrieval_id": frozen["retrieval_id"],
        "grounding_id": frozen["grounding_id"],
        "chunk_sha256": frozen["expected_chunk_sha256"],
        "retrieval_index_sha256": frozen["expected_retrieval_index_sha256"],
    }
    mismatches = [
        key for key, expected_value in expected.items()
        if checks.get(key) != expected_value
    ]
    if mismatches:
        details = ", ".join(
            f"{key}: expected {expected[key]!r}, found {checks.get(key)!r}"
            for key in mismatches
        )
        raise EvaluationError(
            "Frozen RAG artifact identity mismatch. Evaluation stopped without "
            f"retuning or rebuilding: {details}"
        )

    return {
        **checks,
        "index_signature": index_payload.get("index_signature", ""),
        "retrieval_config_fingerprint": index_payload.get("config_fingerprint", ""),
        "retrieval_index_modified": False,
        "grounding_parameters_modified": False,
        "corpus_modified": False,
    }


def run_evaluation(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    retrieval_config_path: Path = DEFAULT_RETRIEVAL_CONFIG_PATH,
    grounding_config_path: Path = DEFAULT_GROUNDING_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Execute the frozen evaluation set and persist one atomic JSON report."""
    config = load_config(config_path)
    report_path = _resolve_project_path(
        project_root,
        config["report_path"],
        "report_path",
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_report = report_path.with_name(report_path.name + ".part")

    # Invalidate stale evidence before a new run. A failed run must not leave a
    # previous successful report that could be mistaken for current evidence.
    for stale in (report_path, temporary_report):
        if stale.exists():
            stale.unlink()

    identity = validate_frozen_artifacts(
        config,
        retrieval_config_path=retrieval_config_path,
        grounding_config_path=grounding_config_path,
        project_root=project_root,
    )
    grounding_config = load_grounding_config(grounding_config_path)

    results: list[dict[str, Any]] = []
    top_k = int(config["retrieval"]["evaluation_top_k"])
    for case in config["cases"]:
        candidates = retrieve(
            case["query"],
            top_k=top_k,
            config_path=retrieval_config_path,
            project_root=project_root,
        )
        reranked = rerank(case["query"], candidates, grounding_config)
        answer = assemble_answer(case["query"], reranked, grounding_config)
        results.append(evaluate_case(case, candidates, reranked, answer, config))

    report = aggregate_results(results, identity, config)
    try:
        temporary_report.write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        temporary_report.replace(report_path)
    except (OSError, UnicodeError) as error:
        if temporary_report.exists():
            temporary_report.unlink()
        raise EvaluationError(f"Unable to write evaluation report: {report_path}") from error
    return report


def _json_for_cli(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen retrieval and citation-grounded answers."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-config")
    validate_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    evaluate_parser.add_argument(
        "--retrieval-config",
        type=Path,
        default=DEFAULT_RETRIEVAL_CONFIG_PATH,
    )
    evaluate_parser.add_argument(
        "--grounding-config",
        type=Path,
        default=DEFAULT_GROUNDING_CONFIG_PATH,
    )
    evaluate_parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-config":
            config = load_config(args.config)
            print(
                _json_for_cli(
                    {
                        "status": "valid",
                        "evaluation_id": config["evaluation_id"],
                        "case_count": len(config["cases"]),
                    }
                )
            )
            return 0
        report = run_evaluation(
            args.config,
            retrieval_config_path=args.retrieval_config,
            grounding_config_path=args.grounding_config,
            project_root=args.project_root,
        )
        print(
            _json_for_cli(
                {
                    "status": report["status"],
                    "evaluation_id": report["evaluation_id"],
                    "failure_case_count": report["failure_case_count"],
                    "retrieval_quality": report["retrieval_quality"],
                    "citation_correctness": report["citation_correctness"],
                    "faithfulness": report["faithfulness"],
                    "answer_usefulness": report["answer_usefulness"],
                    "report_path": str(
                        _resolve_project_path(
                            args.project_root,
                            load_config(args.config)["report_path"],
                            "report_path",
                        )
                    ),
                }
            )
        )
        return 0
    except EvaluationError as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

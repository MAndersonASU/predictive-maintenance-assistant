"""Reproducible vector, keyword, and hybrid retrieval over governed chunks.

This module consumes the governed ``chunks.jsonl`` artifact. It does not
acquire documents, re-extract sources, rerank results, or generate answers.
Every returned result preserves source identity and locator metadata so later
citation-grounded stages can operate without reconstructing provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import sklearn
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "knowledge_retrieval.json"

REQUIRED_CHUNK_FIELDS = {
    "chunk_id",
    "source_id",
    "source_title",
    "publisher",
    "source_url",
    "classification",
    "equipment_relevance",
    "license_or_usage_status",
    "retrieval_identity",
    "scope_note",
    "source_sha256",
    "locator",
    "word_count",
    "text_sha256",
    "text",
}
PRESERVED_RESULT_FIELDS = (
    "chunk_id",
    "source_id",
    "source_title",
    "publisher",
    "source_url",
    "doi",
    "classification",
    "equipment_relevance",
    "license_or_usage_status",
    "retrieval_identity",
    "scope_note",
    "source_sha256",
    "locator",
    "unit_index",
    "unit_chunk_index",
    "source_chunk_index",
    "word_count",
    "text_sha256",
    "text",
)
INDEX_SCHEMA_VERSION = 1


class RetrievalError(RuntimeError):
    """Raised when retrieval governance or reproducibility checks fail."""


@dataclass(frozen=True)
class RetrievalPaths:
    """Resolved project-local retrieval artifact paths."""

    chunks: Path
    index: Path
    report: Path


def sha256_file(path: Path) -> str:
    """Return SHA-256 for a non-empty file."""

    path = Path(path)
    if not path.is_file():
        raise RetrievalError(f"Required file does not exist: {path}")
    if path.stat().st_size == 0:
        raise RetrievalError(f"Required file is empty: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    """Return SHA-256 for UTF-8 text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256_text(payload)


def _array_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(np.asarray(array, dtype="<f8"))
    return hashlib.sha256(contiguous.tobytes(order="C")).hexdigest()


def _require_int(value: Any, label: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise RetrievalError(f"{label} must be an integer >= {minimum}")
    return value


def _require_finite_weight(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise RetrievalError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise RetrievalError(f"{label} must be finite and between 0 and 1")
    return number


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate bounded retrieval parameters before any index is fitted."""

    if config.get("schema_version") != 1:
        raise RetrievalError("schema_version must equal 1")
    for field in (
        "retrieval_id",
        "corpus_id",
        "input_chunk_path",
        "index_path",
        "report_path",
    ):
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RetrievalError(f"{field} must be a non-empty string")

    reproducibility = config.get("reproducibility")
    if not isinstance(reproducibility, dict):
        raise RetrievalError("reproducibility must be an object")
    _require_int(
        reproducibility.get("expected_chunk_count"),
        "reproducibility.expected_chunk_count",
    )
    expected_sha = reproducibility.get("expected_chunk_sha256")
    if (
        not isinstance(expected_sha, str)
        or len(expected_sha) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha)
    ):
        raise RetrievalError(
            "reproducibility.expected_chunk_sha256 must be a lowercase SHA-256 hex digest"
        )

    keyword = config.get("keyword")
    if not isinstance(keyword, dict):
        raise RetrievalError("keyword must be an object")
    if not isinstance(keyword.get("lowercase"), bool):
        raise RetrievalError("keyword.lowercase must be boolean")
    ngram_min = _require_int(keyword.get("ngram_min"), "keyword.ngram_min")
    ngram_max = _require_int(keyword.get("ngram_max"), "keyword.ngram_max")
    if ngram_min > ngram_max:
        raise RetrievalError("keyword.ngram_min cannot exceed keyword.ngram_max")
    _require_int(keyword.get("min_df"), "keyword.min_df")
    _require_int(keyword.get("max_features"), "keyword.max_features")
    if not isinstance(keyword.get("sublinear_tf"), bool):
        raise RetrievalError("keyword.sublinear_tf must be boolean")

    embedding = config.get("embedding")
    if not isinstance(embedding, dict):
        raise RetrievalError("embedding must be an object")
    if embedding.get("method") != "lsa_tfidf":
        raise RetrievalError("embedding.method must equal 'lsa_tfidf'")
    _require_int(embedding.get("dimension"), "embedding.dimension", minimum=2)
    if embedding.get("algorithm") != "randomized":
        raise RetrievalError("embedding.algorithm must equal 'randomized'")
    _require_int(embedding.get("n_iter"), "embedding.n_iter")
    if not isinstance(embedding.get("random_state"), int) or isinstance(
        embedding.get("random_state"), bool
    ):
        raise RetrievalError("embedding.random_state must be an integer")

    hybrid = config.get("hybrid")
    if not isinstance(hybrid, dict):
        raise RetrievalError("hybrid must be an object")
    vector_weight = _require_finite_weight(
        hybrid.get("vector_weight"), "hybrid.vector_weight"
    )
    keyword_weight = _require_finite_weight(
        hybrid.get("keyword_weight"), "hybrid.keyword_weight"
    )
    if not math.isclose(vector_weight + keyword_weight, 1.0, abs_tol=1e-12):
        raise RetrievalError("hybrid weights must sum to 1.0")
    candidate_k = _require_int(hybrid.get("candidate_k"), "hybrid.candidate_k")
    default_top_k = _require_int(
        hybrid.get("default_top_k"), "hybrid.default_top_k"
    )
    maximum_top_k = _require_int(
        hybrid.get("maximum_top_k"), "hybrid.maximum_top_k"
    )
    if default_top_k > maximum_top_k:
        raise RetrievalError("hybrid.default_top_k cannot exceed maximum_top_k")
    if candidate_k < maximum_top_k:
        raise RetrievalError("hybrid.candidate_k must be >= maximum_top_k")

    for field in ("input_chunk_path", "index_path", "report_path"):
        path = Path(config[field])
        if path.is_absolute() or ".." in path.parts:
            raise RetrievalError(f"{field} must stay project-relative")

    return config


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load and validate the governed retrieval configuration."""

    path = Path(path)
    if not path.is_file():
        raise RetrievalError(f"Retrieval config does not exist: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RetrievalError(f"Unable to read retrieval config: {path}") from error
    if not isinstance(config, dict):
        raise RetrievalError("Retrieval config root must be an object")
    return validate_config(config)


def _resolve_project_path(project_root: Path, relative: str, label: str) -> Path:
    root = Path(project_root).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise RetrievalError(f"{label} escapes the project root: {candidate}") from error
    return candidate


def resolve_paths(config: dict[str, Any], project_root: Path) -> RetrievalPaths:
    """Resolve all configured runtime artifacts below the project root."""

    return RetrievalPaths(
        chunks=_resolve_project_path(
            project_root, config["input_chunk_path"], "input_chunk_path"
        ),
        index=_resolve_project_path(project_root, config["index_path"], "index_path"),
        report=_resolve_project_path(project_root, config["report_path"], "report_path"),
    )


def _validate_chunk(chunk: dict[str, Any], index: int) -> None:
    missing = sorted(REQUIRED_CHUNK_FIELDS - set(chunk))
    if missing:
        raise RetrievalError(
            f"Chunk {index} is missing required provenance field(s): " + ", ".join(missing)
        )
    for field in REQUIRED_CHUNK_FIELDS - {"word_count"}:
        if not isinstance(chunk[field], str):
            raise RetrievalError(f"Chunk {index} field {field} must be a string")
    if not chunk["chunk_id"]:
        raise RetrievalError(f"Chunk {index} has an empty chunk_id")
    if not chunk["text"]:
        raise RetrievalError(f"Chunk {index} has empty text")
    if not isinstance(chunk["word_count"], int) or isinstance(chunk["word_count"], bool):
        raise RetrievalError(f"Chunk {index} word_count must be an integer")
    if chunk["word_count"] != len(chunk["text"].split()):
        raise RetrievalError(f"Chunk {index} word_count does not match text")
    if chunk["text_sha256"] != sha256_text(chunk["text"]):
        raise RetrievalError(f"Chunk {index} text checksum does not match text")


def load_governed_chunks(
    path: Path,
    *,
    expected_count: int,
    expected_sha256: str,
) -> list[dict[str, Any]]:
    """Load chunks only when the governed corpus identity matches exactly."""

    actual_sha = sha256_file(path)
    if actual_sha != expected_sha256:
        raise RetrievalError(
            "Governed chunk corpus checksum mismatch. "
            f"Expected {expected_sha256}; found {actual_sha}. "
            "Do not build retrieval evidence from an ungoverned or stale corpus."
        )

    chunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError as error:
                    raise RetrievalError(
                        f"Invalid JSON in chunk corpus at line {line_number}"
                    ) from error
                if not isinstance(chunk, dict):
                    raise RetrievalError(f"Chunk line {line_number} is not an object")
                _validate_chunk(chunk, line_number)
                chunk_id = chunk["chunk_id"]
                if chunk_id in seen_ids:
                    raise RetrievalError(f"Duplicate chunk_id: {chunk_id}")
                seen_ids.add(chunk_id)
                chunks.append(chunk)
    except (OSError, UnicodeError) as error:
        raise RetrievalError(f"Unable to read governed chunks: {path}") from error

    if len(chunks) != expected_count:
        raise RetrievalError(
            f"Governed chunk count mismatch: expected {expected_count}; found {len(chunks)}"
        )
    return chunks


def _fit_vectorizer(config: dict[str, Any], texts: list[str]) -> tuple[TfidfVectorizer, sparse.csr_matrix]:
    keyword = config["keyword"]
    vectorizer = TfidfVectorizer(
        lowercase=keyword["lowercase"],
        ngram_range=(keyword["ngram_min"], keyword["ngram_max"]),
        min_df=keyword["min_df"],
        max_features=keyword["max_features"],
        sublinear_tf=keyword["sublinear_tf"],
        norm="l2",
        dtype=np.float64,
        token_pattern=r"(?u)\b\w\w+\b",
    )
    matrix = vectorizer.fit_transform(texts).tocsr()
    if matrix.shape[1] < 2:
        raise RetrievalError("Keyword vocabulary is too small to build retrieval embeddings")
    return vectorizer, matrix


def _fit_embeddings(
    config: dict[str, Any],
    keyword_matrix: sparse.csr_matrix,
) -> tuple[TruncatedSVD, np.ndarray]:
    embedding = config["embedding"]
    maximum_dimension = min(keyword_matrix.shape[0] - 1, keyword_matrix.shape[1] - 1)
    if maximum_dimension < 2:
        raise RetrievalError("Corpus is too small for a two-dimensional LSA embedding")
    if embedding["dimension"] > maximum_dimension:
        raise RetrievalError(
            f"embedding.dimension={embedding['dimension']} exceeds the deterministic "
            f"corpus limit {maximum_dimension}"
        )
    svd = TruncatedSVD(
        n_components=embedding["dimension"],
        algorithm=embedding["algorithm"],
        n_iter=embedding["n_iter"],
        random_state=embedding["random_state"],
    )
    document_embeddings = svd.fit_transform(keyword_matrix)
    document_embeddings = normalize(document_embeddings, norm="l2", copy=False)
    return svd, np.asarray(document_embeddings, dtype=np.float64)


def _vocabulary_signature(vectorizer: TfidfVectorizer) -> str:
    ordered = sorted(
        ((term, int(index)) for term, index in vectorizer.vocabulary_.items()),
        key=lambda item: item[0],
    )
    payload = {
        "vocabulary": ordered,
        "idf_sha256": _array_sha256(vectorizer.idf_),
    }
    return _canonical_json_sha256(payload)


def _index_signature(
    chunks: list[dict[str, Any]],
    vectorizer: TfidfVectorizer,
    svd: TruncatedSVD,
    document_embeddings: np.ndarray,
) -> str:
    payload = {
        "chunk_ids": [chunk["chunk_id"] for chunk in chunks],
        "vocabulary_sha256": _vocabulary_signature(vectorizer),
        "svd_components_sha256": _array_sha256(svd.components_),
        "document_embeddings_sha256": _array_sha256(document_embeddings),
    }
    return _canonical_json_sha256(payload)


def build_index(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build and persist deterministic keyword + LSA retrieval artifacts."""

    config = load_config(config_path)
    paths = resolve_paths(config, project_root)
    reproducibility = config["reproducibility"]
    chunks = load_governed_chunks(
        paths.chunks,
        expected_count=reproducibility["expected_chunk_count"],
        expected_sha256=reproducibility["expected_chunk_sha256"],
    )
    texts = [chunk["text"] for chunk in chunks]
    vectorizer, keyword_matrix = _fit_vectorizer(config, texts)
    svd, document_embeddings = _fit_embeddings(config, keyword_matrix)

    config_fingerprint = _canonical_json_sha256(config)
    corpus_sha256 = sha256_file(paths.chunks)
    signature = _index_signature(chunks, vectorizer, svd, document_embeddings)

    index_payload = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "retrieval_id": config["retrieval_id"],
        "corpus_id": config["corpus_id"],
        "config_fingerprint": config_fingerprint,
        "corpus_sha256": corpus_sha256,
        "index_signature": signature,
        "chunks": chunks,
        "vectorizer": vectorizer,
        "keyword_matrix": keyword_matrix,
        "svd": svd,
        "document_embeddings": document_embeddings,
    }

    paths.index.parent.mkdir(parents=True, exist_ok=True)
    temporary_index = paths.index.with_name(paths.index.name + ".part")
    if temporary_index.exists():
        temporary_index.unlink()
    joblib.dump(index_payload, temporary_index, compress=3)
    temporary_index.replace(paths.index)

    report = {
        "schema_version": 1,
        "status": "passed",
        "retrieval_id": config["retrieval_id"],
        "corpus_id": config["corpus_id"],
        "corpus_sha256": corpus_sha256,
        "chunk_count": len(chunks),
        "config_fingerprint": config_fingerprint,
        "index_signature": signature,
        "keyword": {
            "vocabulary_size": len(vectorizer.vocabulary_),
            "ngram_range": [config["keyword"]["ngram_min"], config["keyword"]["ngram_max"]],
            "sublinear_tf": config["keyword"]["sublinear_tf"],
            "vocabulary_signature": _vocabulary_signature(vectorizer),
        },
        "embedding": {
            "method": config["embedding"]["method"],
            "dimension": int(document_embeddings.shape[1]),
            "algorithm": config["embedding"]["algorithm"],
            "n_iter": config["embedding"]["n_iter"],
            "random_state": config["embedding"]["random_state"],
            "explained_variance_ratio_sum": float(np.sum(svd.explained_variance_ratio_)),
            "document_embeddings_sha256": _array_sha256(document_embeddings),
            "svd_components_sha256": _array_sha256(svd.components_),
        },
        "hybrid": dict(config["hybrid"]),
        "provenance_preserved_fields": list(PRESERVED_RESULT_FIELDS),
        "scope": {
            "reranking_implemented": False,
            "answer_generation_implemented": False,
            "citation_formatting_implemented": False,
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
    }
    paths.report.parent.mkdir(parents=True, exist_ok=True)
    paths.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def load_index(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    project_root: Path = PROJECT_ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a locally generated index and verify it against current governance."""

    config = load_config(config_path)
    paths = resolve_paths(config, project_root)
    if not paths.index.is_file():
        raise RetrievalError(
            f"Retrieval index does not exist: {paths.index}. Build it before querying."
        )
    try:
        payload = joblib.load(paths.index)
    except Exception as error:
        raise RetrievalError(f"Unable to load retrieval index: {paths.index}") from error
    if not isinstance(payload, dict):
        raise RetrievalError("Retrieval index payload is invalid")
    if payload.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise RetrievalError("Retrieval index schema version mismatch")
    if payload.get("retrieval_id") != config["retrieval_id"]:
        raise RetrievalError("Retrieval index retrieval_id does not match config")
    if payload.get("corpus_id") != config["corpus_id"]:
        raise RetrievalError("Retrieval index corpus_id does not match config")
    expected_fingerprint = _canonical_json_sha256(config)
    if payload.get("config_fingerprint") != expected_fingerprint:
        raise RetrievalError("Retrieval index was built with a different configuration")
    current_corpus_sha = sha256_file(paths.chunks)
    if current_corpus_sha != config["reproducibility"]["expected_chunk_sha256"]:
        raise RetrievalError("Current chunk corpus no longer matches governed checksum")
    if payload.get("corpus_sha256") != current_corpus_sha:
        raise RetrievalError("Retrieval index was built from a different chunk corpus")
    return config, payload


def _bounded_top_indices(scores: np.ndarray, k: int) -> list[int]:
    indexed = [(float(score), index) for index, score in enumerate(scores) if score > 0.0]
    indexed.sort(key=lambda item: (-item[0], item[1]))
    return [index for _, index in indexed[:k]]


def retrieve(
    query: str,
    *,
    top_k: int | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
    project_root: Path = PROJECT_ROOT,
) -> list[dict[str, Any]]:
    """Return deterministic hybrid results with preserved provenance metadata."""

    if not isinstance(query, str) or not query.strip():
        raise RetrievalError("query must be a non-empty string")
    config, payload = load_index(config_path, project_root=project_root)
    hybrid = config["hybrid"]
    if top_k is None:
        top_k = hybrid["default_top_k"]
    _require_int(top_k, "top_k")
    if top_k > hybrid["maximum_top_k"]:
        raise RetrievalError(
            f"top_k={top_k} exceeds configured maximum_top_k={hybrid['maximum_top_k']}"
        )

    vectorizer: TfidfVectorizer = payload["vectorizer"]
    keyword_matrix: sparse.csr_matrix = payload["keyword_matrix"]
    svd: TruncatedSVD = payload["svd"]
    document_embeddings: np.ndarray = payload["document_embeddings"]
    chunks: list[dict[str, Any]] = payload["chunks"]

    query_keyword = vectorizer.transform([query])
    if query_keyword.nnz == 0:
        return []
    keyword_scores = np.asarray((keyword_matrix @ query_keyword.T).toarray()).ravel()

    query_embedding = svd.transform(query_keyword)
    query_embedding = normalize(query_embedding, norm="l2", copy=False)
    vector_scores = np.asarray(document_embeddings @ query_embedding[0]).ravel()
    vector_scores = np.clip(vector_scores, 0.0, 1.0)

    candidate_k = min(hybrid["candidate_k"], len(chunks))
    candidate_indices = set(_bounded_top_indices(keyword_scores, candidate_k))
    candidate_indices.update(_bounded_top_indices(vector_scores, candidate_k))

    ranked: list[tuple[float, float, float, str, int]] = []
    for index in candidate_indices:
        keyword_score = float(keyword_scores[index])
        vector_score = float(vector_scores[index])
        hybrid_score = (
            hybrid["vector_weight"] * vector_score
            + hybrid["keyword_weight"] * keyword_score
        )
        if hybrid_score <= 0.0:
            continue
        ranked.append(
            (
                hybrid_score,
                vector_score,
                keyword_score,
                chunks[index]["chunk_id"],
                index,
            )
        )
    ranked.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3]))

    results: list[dict[str, Any]] = []
    for rank, (hybrid_score, vector_score, keyword_score, _, index) in enumerate(
        ranked[:top_k], start=1
    ):
        chunk = chunks[index]
        result = {
            "rank": rank,
            "hybrid_score": hybrid_score,
            "vector_score": vector_score,
            "keyword_score": keyword_score,
        }
        for field in PRESERVED_RESULT_FIELDS:
            if field in chunk:
                result[field] = chunk[field]
        results.append(result)
    return results


def _json_for_cli(value: Any) -> str:
    """Serialize CLI JSON as ASCII-safe text for Windows console compatibility."""

    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


def _print_json(value: Any) -> None:
    print(_json_for_cli(value))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Project-relative or absolute retrieval config path.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="Build the governed retrieval index and report.")
    query_parser = subparsers.add_parser("query", help="Run one bounded hybrid retrieval query.")
    query_parser.add_argument("query", help="Natural-language retrieval query.")
    query_parser.add_argument("--top-k", type=int, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "build":
        _print_json(build_index(args.config))
        return 0
    if args.command == "query":
        _print_json(retrieve(args.query, top_k=args.top_k, config_path=args.config))
        return 0
    raise RetrievalError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

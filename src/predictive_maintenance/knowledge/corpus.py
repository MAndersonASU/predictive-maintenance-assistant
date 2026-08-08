"""Governed technical-document acquisition, extraction, and chunking."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "knowledge_corpus.json"
DEFAULT_INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "knowledge"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "knowledge_corpus_report.json"
DEFAULT_CHUNK_PATH = DEFAULT_INTERIM_DIR / "chunks.jsonl"
DEFAULT_NORMALIZED_DIR = DEFAULT_INTERIM_DIR / "normalized"

HTTP_USER_AGENT = "predictive-maintenance-assistant/0.1"
REQUEST_TIMEOUT_SECONDS = 60
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
CHECKSUM_CHUNK_SIZE = 1024 * 1024

ALLOWED_CLASSIFICATIONS = {
    "exact_dataset_source",
    "authoritative_general_reference",
}
ALLOWED_FORMATS = {"pdf", "html", "txt"}
ALLOWED_ACQUISITION = {"existing_local", "remote"}
REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "title",
    "publisher",
    "source_url",
    "retrieval_identity",
    "scope_note",
    "license_or_usage_status",
    "equipment_relevance",
    "classification",
    "format",
    "acquisition",
    "local_path",
    "minimum_extracted_words",
    "required_text_markers",
}


class CorpusError(RuntimeError):
    """Raised when corpus governance or processing cannot be completed safely."""


@dataclass(frozen=True)
class ExtractedUnit:
    """One deterministic extraction unit with a source locator."""

    unit_index: int
    locator: str
    text: str


class _VisibleTextHTMLParser(HTMLParser):
    """Collect deterministic visible text while excluding script/style content."""

    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
        "ol",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self._parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style", "noscript", "svg"}:
            self._hidden_depth += 1
            return
        if self._hidden_depth == 0 and normalized_tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"script", "style", "noscript", "svg"}:
            if self._hidden_depth > 0:
                self._hidden_depth -= 1
            return
        if self._hidden_depth == 0 and normalized_tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._hidden_depth == 0:
            self._parts.append(data)

    def visible_text(self) -> str:
        return "".join(self._parts)


def sha256_file(
    path: Path,
    *,
    chunk_size: int = CHECKSUM_CHUNK_SIZE,
) -> str:
    """Return the SHA-256 checksum of a non-empty local file."""

    path = Path(path)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if not path.exists():
        raise CorpusError(f"File does not exist: {path}")
    if not path.is_file():
        raise CorpusError(f"Path is not a file: {path}")
    if path.stat().st_size == 0:
        raise CorpusError(f"File is empty: {path}")

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    """Return the SHA-256 checksum of UTF-8 text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while preserving paragraph boundaries."""

    normalized = unicodedata.normalize("NFKC", text)
    normalized = html.unescape(normalized)
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    paragraphs: list[str] = []
    current_lines: list[str] = []

    def flush() -> None:
        if not current_lines:
            return
        paragraph = " ".join(current_lines)
        paragraph = re.sub(r"[ \t\f\v]+", " ", paragraph).strip()
        if paragraph:
            paragraphs.append(paragraph)
        current_lines.clear()

    for line in normalized.split("\n"):
        stripped = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if stripped:
            current_lines.append(stripped)
        else:
            flush()
    flush()

    return "\n\n".join(paragraphs).strip()


def _require_positive_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CorpusError(f"{field_name} must be a positive integer")
    return value


def validate_corpus_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate and return the governed corpus configuration."""

    if config.get("schema_version") != 1:
        raise CorpusError("schema_version must equal 1")
    if not isinstance(config.get("corpus_id"), str) or not config["corpus_id"].strip():
        raise CorpusError("corpus_id must be a non-empty string")

    chunking = config.get("chunking")
    if not isinstance(chunking, dict):
        raise CorpusError("chunking must be an object")

    max_words = _require_positive_int(chunking.get("max_words"), "chunking.max_words")
    overlap_words = chunking.get("overlap_words")
    if not isinstance(overlap_words, int) or isinstance(overlap_words, bool) or overlap_words < 0:
        raise CorpusError("chunking.overlap_words must be a non-negative integer")
    minimum_words = _require_positive_int(
        chunking.get("minimum_words"),
        "chunking.minimum_words",
    )
    if overlap_words >= max_words:
        raise CorpusError("chunking.overlap_words must be smaller than max_words")
    if minimum_words > max_words:
        raise CorpusError("chunking.minimum_words cannot exceed max_words")

    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        raise CorpusError("sources must be a non-empty list")

    seen_ids: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise CorpusError(f"sources[{index}] must be an object")
        missing = sorted(REQUIRED_SOURCE_FIELDS - set(source))
        if missing:
            raise CorpusError(
                f"sources[{index}] is missing required field(s): "
                + ", ".join(missing)
            )

        string_fields = REQUIRED_SOURCE_FIELDS - {
            "minimum_extracted_words",
            "required_text_markers",
        }
        for field in string_fields:
            value = source[field]
            if not isinstance(value, str) or not value.strip():
                raise CorpusError(
                    f"sources[{index}].{field} must be a non-empty string"
                )

        _require_positive_int(
            source["minimum_extracted_words"],
            f"sources[{index}].minimum_extracted_words",
        )
        required_markers = source["required_text_markers"]
        if (
            not isinstance(required_markers, list)
            or not required_markers
            or any(
                not isinstance(marker, str) or not marker.strip()
                for marker in required_markers
            )
        ):
            raise CorpusError(
                f"sources[{index}].required_text_markers must be a "
                "non-empty list of non-empty strings"
            )

        source_id = source["source_id"].strip()
        if source_id in seen_ids:
            raise CorpusError(f"Duplicate source_id: {source_id}")
        seen_ids.add(source_id)

        if source["classification"] not in ALLOWED_CLASSIFICATIONS:
            raise CorpusError(
                f"Unsupported classification for {source_id}: "
                f"{source['classification']}"
            )
        if source["format"] not in ALLOWED_FORMATS:
            raise CorpusError(
                f"Unsupported format for {source_id}: {source['format']}"
            )
        if source["acquisition"] not in ALLOWED_ACQUISITION:
            raise CorpusError(
                f"Unsupported acquisition mode for {source_id}: "
                f"{source['acquisition']}"
            )

        local_path = Path(source["local_path"])
        if local_path.is_absolute():
            raise CorpusError(
                f"local_path must be project-relative for {source_id}"
            )
        if ".." in local_path.parts:
            raise CorpusError(
                f"local_path cannot escape the project root for {source_id}"
            )

    return config


def load_corpus_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load and validate the governed corpus configuration."""

    path = Path(path)
    if not path.exists():
        raise CorpusError(f"Corpus config does not exist: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CorpusError(f"Unable to read corpus config: {path}") from error
    if not isinstance(config, dict):
        raise CorpusError("Corpus config root must be an object")
    return validate_corpus_config(config)


def resolve_source_path(source: dict[str, Any], project_root: Path) -> Path:
    """Resolve a governed source local path below the project root."""

    project_root = Path(project_root).resolve()
    candidate = (project_root / source["local_path"]).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as error:
        raise CorpusError(
            f"Resolved source path escapes project root: {candidate}"
        ) from error
    return candidate


def download_source(
    url: str,
    destination_path: Path,
    *,
    overwrite: bool = False,
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
) -> Path:
    """Download one remote document atomically."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    destination_path = Path(destination_path)
    if destination_path.exists() and not overwrite:
        return destination_path
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination_path.with_name(destination_path.name + ".part")
    if temporary_path.exists():
        temporary_path.unlink()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": HTTP_USER_AGENT,
            "Accept": "text/html,application/pdf,*/*;q=0.8",
        },
    )

    bytes_written = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", None)
            if status_code not in (None, 200):
                raise CorpusError(
                    f"Unexpected HTTP status {status_code} for {url}"
                )
            with temporary_path.open("wb") as destination:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    destination.write(chunk)
                    bytes_written += len(chunk)
        if bytes_written == 0:
            raise CorpusError(f"Downloaded document is empty: {url}")
        temporary_path.replace(destination_path)
    except CorpusError:
        if temporary_path.exists():
            temporary_path.unlink()
        raise
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as error:
        if temporary_path.exists():
            temporary_path.unlink()
        raise CorpusError(
            "Unable to download governed source. "
            f"Source URL: {url}; destination: {destination_path}"
        ) from error

    return destination_path


def materialize_source(
    source: dict[str, Any],
    *,
    project_root: Path,
    offline: bool = False,
    overwrite_downloads: bool = False,
) -> Path:
    """Ensure one governed source exists locally without altering existing input."""

    destination = resolve_source_path(source, project_root)
    acquisition = source["acquisition"]

    if acquisition == "existing_local":
        if not destination.exists():
            raise CorpusError(
                "Required existing source is missing. "
                f"Expected: {destination}. This project source should already "
                "exist from governed MetroPT acquisition."
            )
        sha256_file(destination)
        return destination

    if destination.exists() and not overwrite_downloads:
        sha256_file(destination)
        return destination

    if offline:
        raise CorpusError(
            f"Remote source is not available locally in offline mode: {destination}"
        )

    downloaded = download_source(
        source["source_url"],
        destination,
        overwrite=overwrite_downloads,
    )
    sha256_file(downloaded)
    return downloaded


def extract_pdf_units(path: Path) -> list[ExtractedUnit]:
    """Extract normalized text page by page from a PDF."""

    try:
        reader = PdfReader(str(path))
    except Exception as error:
        raise CorpusError(f"Unable to open PDF: {path}") from error

    units: list[ExtractedUnit] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception as error:
            raise CorpusError(
                f"Unable to extract PDF page {page_number}: {path}"
            ) from error
        normalized = normalize_text(raw_text)
        if normalized:
            units.append(
                ExtractedUnit(
                    unit_index=page_number,
                    locator=f"page:{page_number}",
                    text=normalized,
                )
            )

    if not units:
        raise CorpusError(
            f"PDF produced no extractable text: {path}. "
            "Scanned-image OCR is intentionally outside this deterministic corpus pipeline."
        )
    return units


def extract_html_units(path: Path) -> list[ExtractedUnit]:
    """Extract deterministic visible text from an HTML document."""

    try:
        raw_html = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise CorpusError(f"Unable to read HTML: {path}") from error

    parser = _VisibleTextHTMLParser()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception as error:
        raise CorpusError(f"Unable to parse HTML: {path}") from error

    normalized = normalize_text(parser.visible_text())
    if not normalized:
        raise CorpusError(f"HTML produced no visible text: {path}")
    return [ExtractedUnit(unit_index=1, locator="document", text=normalized)]


def extract_txt_units(path: Path) -> list[ExtractedUnit]:
    """Extract one normalized unit from a UTF-8 text document."""

    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise CorpusError(f"Unable to read text source: {path}") from error
    normalized = normalize_text(raw_text)
    if not normalized:
        raise CorpusError(f"Text source is empty after normalization: {path}")
    return [ExtractedUnit(unit_index=1, locator="document", text=normalized)]


def extract_source_units(
    path: Path,
    source_format: str,
) -> list[ExtractedUnit]:
    """Dispatch deterministic extraction for the governed source format."""

    if source_format == "pdf":
        return extract_pdf_units(path)
    if source_format == "html":
        return extract_html_units(path)
    if source_format == "txt":
        return extract_txt_units(path)
    raise CorpusError(f"Unsupported source format: {source_format}")


def validate_extracted_source(
    source: dict[str, Any],
    units: Iterable[ExtractedUnit],
) -> dict[str, Any]:
    """Reject incomplete/interstitial extraction before chunking."""

    unit_list = list(units)
    combined_text = "\n\n".join(unit.text for unit in unit_list)
    word_count = len(combined_text.split())
    minimum_words = source["minimum_extracted_words"]
    if word_count < minimum_words:
        raise CorpusError(
            f"Extracted content is too short for {source['source_id']}: "
            f"{word_count} words; minimum required is {minimum_words}. "
            "The retrieved file may be a landing page, interstitial, or "
            "incomplete source."
        )

    missing_markers = [
        marker
        for marker in source["required_text_markers"]
        if marker.casefold() not in combined_text.casefold()
    ]
    if missing_markers:
        raise CorpusError(
            f"Extracted content for {source['source_id']} is missing "
            "required marker(s): " + ", ".join(missing_markers)
        )

    return {
        "status": "passed",
        "extracted_word_count": word_count,
        "minimum_extracted_words": minimum_words,
        "required_text_markers": list(source["required_text_markers"]),
    }


def _words(text: str) -> list[str]:
    return text.split()


def chunk_unit_text(
    text: str,
    *,
    max_words: int,
    overlap_words: int,
    minimum_words: int,
) -> list[str]:
    """Split one extraction unit deterministically with bounded word overlap."""

    max_words = _require_positive_int(max_words, "max_words")
    minimum_words = _require_positive_int(minimum_words, "minimum_words")
    if not isinstance(overlap_words, int) or isinstance(overlap_words, bool) or overlap_words < 0:
        raise CorpusError("overlap_words must be a non-negative integer")
    if overlap_words >= max_words:
        raise CorpusError("overlap_words must be smaller than max_words")
    if minimum_words > max_words:
        raise CorpusError("minimum_words cannot exceed max_words")

    words = _words(normalize_text(text))
    if not words:
        return []
    if len(words) <= max_words:
        return [" ".join(words)]

    step = max_words - overlap_words
    chunks: list[list[str]] = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        current = words[start:end]
        if not current:
            break
        chunks.append(current)
        if end == len(words):
            break
        start += step

    if len(chunks) >= 2 and len(chunks[-1]) < minimum_words:
        previous = chunks[-2]
        tail = chunks[-1]
        merged = previous + tail[overlap_words:]
        if len(merged) <= max_words:
            chunks[-2] = merged
            chunks.pop()

    return [" ".join(chunk) for chunk in chunks]


def build_chunks_for_source(
    source: dict[str, Any],
    source_checksum: str,
    units: Iterable[ExtractedUnit],
    chunking: dict[str, int],
) -> list[dict[str, Any]]:
    """Create provenance-preserving chunks for one governed source."""

    chunks: list[dict[str, Any]] = []
    global_index = 0
    for unit in units:
        unit_chunks = chunk_unit_text(
            unit.text,
            max_words=chunking["max_words"],
            overlap_words=chunking["overlap_words"],
            minimum_words=chunking["minimum_words"],
        )
        for unit_chunk_index, text in enumerate(unit_chunks, start=1):
            global_index += 1
            text_checksum = sha256_text(text)
            chunk_id = (
                f"{source['source_id']}::u{unit.unit_index:04d}::"
                f"c{unit_chunk_index:04d}::{text_checksum[:12]}"
            )
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "source_id": source["source_id"],
                    "source_title": source["title"],
                    "publisher": source["publisher"],
                    "source_url": source["source_url"],
                    "doi": source.get("doi", ""),
                    "classification": source["classification"],
                    "equipment_relevance": source["equipment_relevance"],
                    "license_or_usage_status": source["license_or_usage_status"],
                    "retrieval_identity": source["retrieval_identity"],
                    "scope_note": source["scope_note"],
                    "source_sha256": source_checksum,
                    "locator": unit.locator,
                    "unit_index": unit.unit_index,
                    "unit_chunk_index": unit_chunk_index,
                    "source_chunk_index": global_index,
                    "word_count": len(_words(text)),
                    "text_sha256": text_checksum,
                    "text": text,
                }
            )
    if not chunks:
        raise CorpusError(
            f"Source produced zero chunks: {source['source_id']}"
        )
    return chunks


def validate_chunk_records(chunks: list[dict[str, Any]]) -> None:
    """Verify chunk identifiers, checksums, provenance, and safety metadata."""

    if not chunks:
        raise CorpusError("Chunk collection is empty")

    ids: set[str] = set()
    required = {
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

    for index, chunk in enumerate(chunks):
        missing = sorted(required - set(chunk))
        if missing:
            raise CorpusError(
                f"Chunk {index} is missing field(s): " + ", ".join(missing)
            )
        chunk_id = chunk["chunk_id"]
        if chunk_id in ids:
            raise CorpusError(f"Duplicate chunk_id: {chunk_id}")
        ids.add(chunk_id)
        if chunk["classification"] not in ALLOWED_CLASSIFICATIONS:
            raise CorpusError(
                f"Chunk {chunk_id} has unsupported classification"
            )
        if sha256_text(chunk["text"]) != chunk["text_sha256"]:
            raise CorpusError(f"Chunk text checksum mismatch: {chunk_id}")
        if len(chunk["source_sha256"]) != 64:
            raise CorpusError(f"Invalid source checksum on chunk: {chunk_id}")
        if chunk["word_count"] != len(_words(chunk["text"])):
            raise CorpusError(f"Chunk word count mismatch: {chunk_id}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".part")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        temporary_path.write_text(text, encoding="utf-8", newline="\n")
        temporary_path.replace(path)
    except OSError as error:
        if temporary_path.exists():
            temporary_path.unlink()
        raise CorpusError(f"Unable to write output: {path}") from error


def write_chunks_jsonl(chunks: list[dict[str, Any]], path: Path) -> Path:
    """Write canonical UTF-8 JSON Lines chunk records atomically."""

    validate_chunk_records(chunks)
    lines = [
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for record in chunks
    ]
    _atomic_write_text(path, "\n".join(lines) + "\n")
    return path


def write_normalized_source(
    source_id: str,
    units: list[ExtractedUnit],
    normalized_dir: Path,
) -> Path:
    """Write deterministic normalized text with explicit unit locators."""

    parts: list[str] = []
    for unit in units:
        parts.append(f"===== {unit.locator} =====")
        parts.append(unit.text)
    path = normalized_dir / f"{source_id}.txt"
    _atomic_write_text(path, "\n\n".join(parts).strip() + "\n")
    return path




def invalidate_generated_corpus_evidence(
    *,
    interim_dir: Path,
    report_path: Path,
) -> None:
    """Remove prior generated corpus evidence before a new governed run.

    A failed refresh must never leave an older successful report or chunk file
    available to be mistaken for evidence from the failed run. Raw governed
    source files are intentionally untouched.
    """

    interim_dir = Path(interim_dir)
    report_path = Path(report_path)

    if report_path.exists():
        if not report_path.is_file():
            raise CorpusError(f"Report path is not a file: {report_path}")
        report_path.unlink()

    if interim_dir.exists():
        if not interim_dir.is_dir():
            raise CorpusError(f"Interim knowledge path is not a directory: {interim_dir}")
        shutil.rmtree(interim_dir)

def _config_checksum(config: dict[str, Any]) -> str:
    canonical = json.dumps(
        config,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(canonical)


def run_corpus_workflow(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    project_root: Path = PROJECT_ROOT,
    interim_dir: Path | None = None,
    report_path: Path | None = None,
    offline: bool = False,
    overwrite_downloads: bool = False,
) -> dict[str, Any]:
    """Materialize, extract, normalize, chunk, and report the governed corpus."""

    project_root = Path(project_root).resolve()
    config = load_corpus_config(config_path)
    chunking = config["chunking"]

    if interim_dir is None:
        interim_dir = project_root / "data" / "interim" / "knowledge"
    else:
        interim_dir = Path(interim_dir)
    if report_path is None:
        report_path = project_root / "outputs" / "knowledge_corpus_report.json"
    else:
        report_path = Path(report_path)

    chunk_path = interim_dir / "chunks.jsonl"
    normalized_dir = interim_dir / "normalized"

    invalidate_generated_corpus_evidence(
        interim_dir=interim_dir,
        report_path=report_path,
    )

    all_chunks: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []

    for source in config["sources"]:
        source_path = materialize_source(
            source,
            project_root=project_root,
            offline=offline,
            overwrite_downloads=overwrite_downloads,
        )
        source_checksum = sha256_file(source_path)
        units = extract_source_units(source_path, source["format"])
        content_validation = validate_extracted_source(source, units)
        normalized_path = write_normalized_source(
            source["source_id"],
            units,
            normalized_dir,
        )
        chunks = build_chunks_for_source(
            source,
            source_checksum,
            units,
            chunking,
        )
        all_chunks.extend(chunks)
        source_reports.append(
            {
                "source_id": source["source_id"],
                "title": source["title"],
                "publisher": source["publisher"],
                "source_url": source["source_url"],
                "doi": source.get("doi", ""),
                "classification": source["classification"],
                "equipment_relevance": source["equipment_relevance"],
                "license_or_usage_status": source["license_or_usage_status"],
                "retrieval_identity": source["retrieval_identity"],
                "scope_note": source["scope_note"],
                "local_path": source["local_path"],
                "local_status": "materialized_and_verified",
                "source_sha256": source_checksum,
                "extracted_unit_count": len(units),
                "extracted_word_count": content_validation["extracted_word_count"],
                "content_validation": content_validation["status"],
                "minimum_extracted_words": content_validation["minimum_extracted_words"],
                "required_text_markers": content_validation["required_text_markers"],
                "chunk_count": len(chunks),
                "normalized_text_sha256": sha256_file(normalized_path),
            }
        )

    validate_chunk_records(all_chunks)
    write_chunks_jsonl(all_chunks, chunk_path)

    report = {
        "schema_version": 1,
        "corpus_id": config["corpus_id"],
        "config_sha256": _config_checksum(config),
        "source_count": len(source_reports),
        "chunk_count": len(all_chunks),
        "chunking": chunking,
        "chunks_path": str(chunk_path.relative_to(project_root)),
        "chunks_sha256": sha256_file(chunk_path),
        "sources": source_reports,
        "provenance_validation": "passed",
        "determinism_note": (
            "Report contains no run timestamp; identical governed inputs and "
            "configuration produce identical normalized text and chunk bytes."
        ),
        "safety_boundary": (
            "General authoritative references are not exact MetroPT equipment "
            "manuals and must not be represented as equipment-specific instructions."
        ),
    }
    report_text = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    _atomic_write_text(report_path, report_text)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build the governed technical-document corpus and deterministic chunks."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the governed corpus configuration.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Refuse network access and require all sources to exist locally.",
    )
    parser.add_argument(
        "--overwrite-downloads",
        action="store_true",
        help="Redownload remote sources even when a local file already exists.",
    )
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    report = run_corpus_workflow(
        args.config,
        offline=args.offline,
        overwrite_downloads=args.overwrite_downloads,
    )
    print(
        "Governed knowledge corpus complete: "
        f"{report['source_count']} sources, {report['chunk_count']} chunks, "
        f"chunk SHA-256 {report['chunks_sha256']}"
    )


if __name__ == "__main__":
    main()

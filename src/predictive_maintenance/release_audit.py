"""Deterministic release-candidate audit for the bounded local system.

This module validates committed release controls and the identities of the
externally governed runtime artifacts. It does not fit a model, rebuild the
knowledge corpus or retrieval index, or execute either held-out evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXPECTED_CANDIDATE_ID = "iforest_ne200_ms4096_mf1p0"
EXPECTED_THRESHOLD = 0.601902290159477
EXPECTED_FEATURE_COUNT = 48
EXPECTED_CHUNK_COUNT = 354
EXPECTED_MODEL_SHA256 = "fa23b81d214161488abf601a8b9852f2467347e53d02fca3653a13cdaaaeec1a"
EXPECTED_CHUNK_SHA256 = "4912c36622d38d44100c3965f457cb45e7de44358d9626c9558ca25b24be722d"
EXPECTED_INDEX_SHA256 = "2700dac28adfc9a80a9bd28c3af177237d45e845ef94c37cd4e68b421d4442b7"

REQUIRED_RELEASE_DOCUMENTS = (
    "README.md",
    "docs/data_card.md",
    "docs/model_card.md",
    "docs/evaluation_summary.md",
    "docs/deployment_guide.md",
    "docs/system_architecture.md",
    "docs/portfolio_interview_guide.md",
    "docs/release_candidate_checklist.md",
)


@dataclass(frozen=True)
class AuditCheck:
    """One independently reviewable audit result."""

    check_id: str
    passed: bool
    detail: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _configured_artifacts(config: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    prediction = config["prediction"]
    knowledge = config["knowledge"]
    yield "model", prediction["model_path"], prediction["model_sha256"]
    yield "chunk_corpus", knowledge["chunk_path"], knowledge["chunk_sha256"]
    yield "retrieval_index", knowledge["retrieval_index_path"], knowledge["retrieval_index_sha256"]


def run_release_audit(repository_root: Path) -> dict[str, Any]:
    """Audit one prepared local release candidate without changing it."""

    root = Path(repository_root).resolve()
    checks: list[AuditCheck] = []

    for relative_path in REQUIRED_RELEASE_DOCUMENTS:
        path = root / relative_path
        checks.append(
            AuditCheck(
                check_id=f"document:{relative_path}",
                passed=path.is_file() and path.stat().st_size > 0,
                detail="present and non-empty" if path.is_file() and path.stat().st_size > 0 else "missing or empty",
            )
        )

    config_path = root / "config" / "application.json"
    try:
        config = _load_json(config_path)
        prediction = config["prediction"]
        knowledge = config["knowledge"]
        security = config["security"]
        contract_matches = (
            prediction["candidate_id"] == EXPECTED_CANDIDATE_ID
            and prediction["threshold"] == EXPECTED_THRESHOLD
            and prediction["retained_feature_count"] == EXPECTED_FEATURE_COUNT
            and prediction["model_sha256"] == EXPECTED_MODEL_SHA256
            and knowledge["chunk_sha256"] == EXPECTED_CHUNK_SHA256
            and knowledge["retrieval_index_sha256"] == EXPECTED_INDEX_SHA256
        )
        checks.append(AuditCheck("frozen_contract", contract_matches, "frozen identifiers match" if contract_matches else "frozen identifiers drifted"))
        local_boundary = (
            config["server"]["require_loopback_bind"] is True
            and config["server"]["host"] in {"127.0.0.1", "localhost", "::1"}
            and security["public_network_exposure_allowed"] is False
            and security["persist_raw_feature_values"] is False
            and security["persist_request_headers"] is False
        )
        checks.append(AuditCheck("bounded_local_security", local_boundary, "loopback and privacy boundaries preserved" if local_boundary else "local security boundary drifted"))
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        config = None
        checks.append(AuditCheck("application_config", False, f"unable to validate: {type(error).__name__}"))

    if config is not None:
        for label, relative_path, expected_hash in _configured_artifacts(config):
            path = root / relative_path
            if not path.is_file():
                checks.append(AuditCheck(f"artifact:{label}", False, f"missing: {relative_path}"))
                continue
            actual_hash = _sha256(path)
            checks.append(
                AuditCheck(
                    f"artifact:{label}",
                    actual_hash == expected_hash,
                    f"SHA-256 {actual_hash}",
                )
            )

        chunk_path = root / config["knowledge"]["chunk_path"]
        if chunk_path.is_file():
            chunk_count = sum(1 for line in chunk_path.read_text(encoding="utf-8").splitlines() if line.strip())
            checks.append(
                AuditCheck(
                    "chunk_count",
                    chunk_count == EXPECTED_CHUNK_COUNT,
                    f"{chunk_count} non-empty records",
                )
            )

    asset_paths = (
        root / "src/predictive_maintenance/application/demo_assets/index.html",
        root / "src/predictive_maintenance/application/demo_assets/app.js",
        root / "src/predictive_maintenance/application/demo_assets/styles.css",
    )
    assets_present = all(path.is_file() and path.stat().st_size > 0 for path in asset_paths)
    prohibited_tokens = ("localStorage", "sessionStorage", "https://", "http://")
    assets_self_contained = assets_present and all(
        token not in path.read_text(encoding="utf-8")
        for path in asset_paths
        for token in prohibited_tokens
    )
    checks.append(
        AuditCheck(
            "self_contained_interface",
            assets_self_contained,
            "assets present with no remote URL or browser persistence token" if assets_self_contained else "asset boundary failed",
        )
    )

    passed = all(check.passed for check in checks)
    return {
        "schema_version": 1,
        "audit_id": "bounded_local_release_candidate_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(root),
        "held_out_evaluator_executed": False,
        "model_or_index_rebuilt": False,
        "status": "passed" if passed else "failed",
        "check_count": len(checks),
        "passed_count": sum(check.passed for check in checks),
        "checks": [asdict(check) for check in checks],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("outputs/release_candidate_audit.json"))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    report = run_release_audit(args.repository_root)
    output = args.output if args.output.is_absolute() else args.repository_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": report["check_count"], "passed": report["passed_count"], "report": str(output)}, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

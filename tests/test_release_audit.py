from __future__ import annotations

import hashlib
import json
from pathlib import Path

from predictive_maintenance.release_audit import REQUIRED_RELEASE_DOCUMENTS, run_release_audit


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _prepared_repository(root: Path) -> None:
    for relative_path in REQUIRED_RELEASE_DOCUMENTS:
        _write(root / relative_path, "verified release documentation\n")

    model = b"model"
    chunks = (b'{"chunk": 1}\n' * 354)
    index = b"index"
    _write(root / "outputs/model.joblib", model)
    _write(root / "data/chunks.jsonl", chunks)
    _write(root / "data/index.joblib", index)
    for asset in ("index.html", "app.js", "styles.css"):
        _write(root / f"src/predictive_maintenance/application/demo_assets/{asset}", "self contained\n")

    config = {
        "server": {"require_loopback_bind": True, "host": "127.0.0.1"},
        "prediction": {
            "candidate_id": "iforest_ne200_ms4096_mf1p0",
            "threshold": 0.601902290159477,
            "retained_feature_count": 48,
            "model_path": "outputs/model.joblib",
            "model_sha256": _sha256(model),
        },
        "knowledge": {
            "chunk_path": "data/chunks.jsonl",
            "chunk_sha256": _sha256(chunks),
            "retrieval_index_path": "data/index.joblib",
            "retrieval_index_sha256": _sha256(index),
        },
        "security": {
            "public_network_exposure_allowed": False,
            "persist_raw_feature_values": False,
            "persist_request_headers": False,
        },
    }
    # The production frozen hashes are immutable. The fixture replaces the
    # bytes and then patches only the module constants during its test.
    _write(root / "config/application.json", json.dumps(config))


def test_release_audit_passes_for_complete_prepared_release(tmp_path: Path, monkeypatch) -> None:
    _prepared_repository(tmp_path)
    config = json.loads((tmp_path / "config/application.json").read_text(encoding="utf-8"))
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_MODEL_SHA256", config["prediction"]["model_sha256"])
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_CHUNK_SHA256", config["knowledge"]["chunk_sha256"])
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_INDEX_SHA256", config["knowledge"]["retrieval_index_sha256"])

    report = run_release_audit(tmp_path)

    assert report["status"] == "passed"
    assert report["passed_count"] == report["check_count"]
    assert report["held_out_evaluator_executed"] is False
    assert report["model_or_index_rebuilt"] is False


def test_release_audit_reports_missing_artifact(tmp_path: Path, monkeypatch) -> None:
    _prepared_repository(tmp_path)
    config = json.loads((tmp_path / "config/application.json").read_text(encoding="utf-8"))
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_MODEL_SHA256", config["prediction"]["model_sha256"])
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_CHUNK_SHA256", config["knowledge"]["chunk_sha256"])
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_INDEX_SHA256", config["knowledge"]["retrieval_index_sha256"])
    (tmp_path / "data/index.joblib").unlink()

    report = run_release_audit(tmp_path)

    assert report["status"] == "failed"
    failed = {item["check_id"] for item in report["checks"] if not item["passed"]}
    assert "artifact:retrieval_index" in failed


def test_release_audit_rejects_remote_interface_dependency(tmp_path: Path, monkeypatch) -> None:
    _prepared_repository(tmp_path)
    config = json.loads((tmp_path / "config/application.json").read_text(encoding="utf-8"))
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_MODEL_SHA256", config["prediction"]["model_sha256"])
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_CHUNK_SHA256", config["knowledge"]["chunk_sha256"])
    monkeypatch.setattr("predictive_maintenance.release_audit.EXPECTED_INDEX_SHA256", config["knowledge"]["retrieval_index_sha256"])
    _write(tmp_path / "src/predictive_maintenance/application/demo_assets/app.js", "fetch('https://example.invalid')\n")

    report = run_release_audit(tmp_path)

    assert report["status"] == "failed"
    failed = {item["check_id"] for item in report["checks"] if not item["passed"]}
    assert "self_contained_interface" in failed

"""Static contract tests for bounded reproducible container execution."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _requirement_versions(relative_path: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw_line in _read(relative_path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        assert "==" in line, f"Unpinned dependency in {relative_path}: {line}"
        name, version = line.split("==", 1)
        versions[name.lower()] = version
    return versions


def test_dockerfile_pins_governed_build_frontend_and_python_base_image() -> None:
    dockerfile = _read("Dockerfile")
    assert (
        "# syntax=docker/dockerfile:1@"
        "sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89"
    ) in dockerfile
    expected = (
        "FROM python:3.14.6-slim-bookworm@"
        "sha256:86f975aca15cf04a40b399eebede9aea7c82eae084d1f1a0a6ef6bcaae871a30"
    )
    assert expected in dockerfile
    assert "COPY ." not in dockerfile
    assert "requirements.txt" in dockerfile
    assert "requirements-container.txt" in dockerfile
    assert "src/ /app/src/" in dockerfile
    assert "config/ /app/config/" in dockerfile


def test_dockerfile_installs_fully_pinned_container_runtime_contract() -> None:
    dockerfile = _read("Dockerfile")
    assert "COPY --chown=appuser:appuser requirements-container.txt /app/requirements-container.txt" in dockerfile
    assert "--root-user-action=ignore" in dockerfile
    assert "--requirement /app/requirements-container.txt" in dockerfile
    assert "--requirement /app/requirements.txt" not in dockerfile


def test_container_runtime_lock_matches_governed_verification_versions() -> None:
    direct = _requirement_versions("requirements.txt")
    locked = _requirement_versions("requirements-container.txt")
    expected_transitive = {
        "numpy": "2.4.6",
        "scipy": "1.18.0",
        "joblib": "1.5.3",
        "threadpoolctl": "3.6.0",
        "starlette": "1.3.1",
        "anyio": "4.14.2",
        "h11": "0.16.0",
        "idna": "3.18",
        "annotated-doc": "0.0.4",
        "annotated-types": "0.7.0",
        "pydantic-core": "2.46.4",
        "typing-extensions": "4.16.0",
        "typing-inspection": "0.4.2",
        "click": "8.4.2",
    }
    assert locked == expected_transitive
    assert not (set(direct) & set(locked))
    assert "-r requirements.txt" in _read("requirements-container.txt")


def test_dockerfile_runs_unprivileged_and_has_readiness_healthcheck() -> None:
    dockerfile = _read("Dockerfile")
    assert "USER 10001:10001" in dockerfile
    assert "/health/ready" in dockerfile
    assert '"--factory"' in dockerfile
    assert '"--host", "0.0.0.0"' in dockerfile
    assert '"--port", "8000"' in dockerfile


def test_dockerignore_is_deny_all_with_narrow_runtime_allowlist() -> None:
    lines = [line.strip() for line in _read(".dockerignore").splitlines() if line.strip() and not line.startswith("#")]
    assert lines[0] == "**"
    assert set(lines[1:]) == {
        "!Dockerfile",
        "!.dockerignore",
        "!requirements.txt",
        "!requirements-container.txt",
        "!src/",
        "!src/**",
        "!config/",
        "!config/**",
    }
    assert not any(line in {"!data/", "!data/**", "!outputs/", "!outputs/**", "!.env", "!.env.*"} for line in lines)


def test_compose_publishes_only_on_host_loopback() -> None:
    compose = _read("compose.yaml")
    assert '"127.0.0.1:8000:8000"' in compose
    assert re.search(r"(?m)^\s*-\s*[\"']?8000:8000[\"']?\s*$", compose) is None
    assert "network_mode: host" not in compose


def test_compose_hardens_container_runtime() -> None:
    compose = _read("compose.yaml")
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert re.search(r"(?ms)cap_drop:\s*\n\s*- ALL", compose)
    assert re.search(r"(?ms)tmpfs:\s*\n\s*- /tmp", compose)


def test_governed_artifacts_are_read_only_bind_mounts_without_auto_creation() -> None:
    compose = _read("compose.yaml")
    required_sources = [
        "./outputs/metropt3_selected_isolation_forest.joblib",
        "./outputs/metropt3_robust_distance_parameters.json",
        "./outputs/metropt3_isolation_forest_validation_report.json",
        "./data/interim/knowledge/chunks.jsonl",
        "./data/interim/knowledge/retrieval/hybrid_index.joblib",
    ]
    for source in required_sources:
        start = compose.index(f"source: {source}")
        next_mount = compose.find("\n      - type:", start + 1)
        block = compose[start:] if next_mount == -1 else compose[start:next_mount]
        assert "type: bind" in compose[max(0, start - 40):start]
        assert "read_only: true" in block
        assert "create_host_path: false" in block


def test_application_state_is_the_only_named_writable_data_mount() -> None:
    compose = _read("compose.yaml")
    assert "source: application_state" in compose
    assert "target: /app/data/interim/application" in compose
    assert re.search(r"(?m)^\s{2}application_state:\s*$", compose)


def test_deployment_document_preserves_truthful_scope_and_clean_startup_evidence() -> None:
    document = _read("docs/container_execution.md")
    required_phrases = [
        "bounded local demonstration",
        "does not refit",
        "read-only",
        "127.0.0.1:8000:8000",
        "requirements-container.txt",
        "NumPy 2.4.6",
        "Starlette 1.3.1",
        "docker compose config --quiet",
        "docker compose build --no-cache",
        "/health/live",
        "/health/ready",
        "not a public service",
        "Authentication remains disabled",
    ]
    for phrase in required_phrases:
        assert phrase in document

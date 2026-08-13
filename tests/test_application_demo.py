"""Contract tests for the self-contained professional demonstration interface."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from predictive_maintenance.application.demo import DEMO_ASSET_ROOT, register_demo_routes


def _client() -> TestClient:
    app = FastAPI()
    register_demo_routes(app)
    return TestClient(app)


def test_demo_assets_are_complete_and_local() -> None:
    expected = {"index.html", "styles.css", "app.js"}
    assert {path.name for path in DEMO_ASSET_ROOT.iterdir() if path.is_file()} == expected
    for name in expected:
        content = (DEMO_ASSET_ROOT / name).read_text(encoding="utf-8")
        assert "http://" not in content
        assert "https://" not in content


def test_demo_root_presents_prediction_knowledge_and_operations_workspaces() -> None:
    with _client() as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Knowledge + evidence" in response.text
    assert "Prediction" in response.text
    assert "Operations" in response.text
    assert "unusualness is not failure probability" in response.text


def test_demo_root_has_bounded_security_headers() -> None:
    with _client() as client:
        response = client.get("/")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "connect-src 'self'" in response.headers["content-security-policy"]


def test_demo_stylesheet_and_script_are_served_with_explicit_types() -> None:
    with _client() as client:
        stylesheet = client.get("/demo/styles.css")
        script = client.get("/demo/app.js")
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("application/javascript")


def test_unknown_demo_asset_is_not_exposed() -> None:
    with _client() as client:
        response = client.get("/demo/config.json")
    assert response.status_code == 404
    assert "application_id" not in response.text


def test_demo_uses_only_governed_api_paths() -> None:
    script = (DEMO_ASSET_ROOT / "app.js").read_text(encoding="utf-8")
    required_paths = {
        "/health/ready",
        "/api/v1/prediction/schema",
        "/api/v1/predict",
        "/api/v1/retrieve",
        "/api/v1/answer",
        "/api/v1/evaluations?limit=1",
        "/api/v1/metrics",
    }
    for path in required_paths:
        assert path in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script


def test_demo_has_no_inline_script_or_event_handler() -> None:
    html = (DEMO_ASSET_ROOT / "index.html").read_text(encoding="utf-8")
    assert "<script src=\"/demo/app.js\" defer></script>" in html
    assert "onclick=" not in html
    assert "onload=" not in html
    assert "<style" not in html


def test_documented_module_startup_has_no_preimport_runtime_warning() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-m",
            "predictive_maintenance.application.api",
            "--help",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "RuntimeWarning" not in result.stderr

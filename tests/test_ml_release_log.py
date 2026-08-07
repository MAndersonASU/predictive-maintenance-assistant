from __future__ import annotations

import importlib
import pytest


def test_commit_sha_validation_shape():
    module = importlib.import_module("predictive_maintenance.analysis.ml_release_log")
    assert module.MARKER == "### Frozen Machine-Learning Release"


def test_log_error_is_value_error():
    module = importlib.import_module("predictive_maintenance.analysis.ml_release_log")
    assert issubclass(module.MLReleaseLogError, ValueError)

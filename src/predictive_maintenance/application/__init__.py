"""Application integration layer for the predictive-maintenance assistant."""

from __future__ import annotations

from typing import Any

__all__ = ["create_app"]


def __getattr__(name: str) -> Any:
    """Load the app factory lazily so ``python -m ...application.api`` is warning-free."""
    if name == "create_app":
        from .api import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

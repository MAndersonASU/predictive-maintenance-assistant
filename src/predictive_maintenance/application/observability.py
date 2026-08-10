"""Structured logging and bounded in-process monitoring counters."""

from __future__ import annotations

import json
import logging
import sys
import threading
from collections import Counter
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class JsonFormatter(logging.Formatter):
    """Emit one compact JSON object per application log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": utc_now(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("request_id", "event_name", "operation", "status", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def build_logger(name: str = "predictive_maintenance.application") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(getattr(handler, "_predictive_json_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        handler._predictive_json_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    return logger


class MetricsRegistry:
    """Thread-safe bounded counters for local demonstration monitoring."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Counter[str] = Counter()

    def increment(self, name: str, amount: int = 1) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("metric name must be non-empty")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
            raise ValueError("metric increment must be a positive integer")
        with self._lock:
            self._counters[name] += amount

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(sorted(self._counters.items()))

"""Bounded local SQLite persistence for demonstration interactions and events."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .observability import utc_now


class PersistenceError(RuntimeError):
    """Raised when bounded local persistence cannot complete safely."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


class SQLiteStore:
    """Small local record/event store with deterministic retention limits."""

    def __init__(
        self, path: Path, *, max_records: int, max_evaluations: int, max_events: int
    ) -> None:
        self.path = Path(path)
        self.max_records = int(max_records)
        self.max_evaluations = int(max_evaluations)
        self.max_events = int(max_events)
        if min(self.max_records, self.max_evaluations, self.max_events) < 1:
            raise PersistenceError("Retention limits must be positive")

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self.path, timeout=5.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            return connection
        except sqlite3.Error as error:
            raise PersistenceError(f"Unable to open local SQLite database: {self.path}") from error

    @contextmanager
    def _connection(self):
        """Yield one transaction-scoped connection and always close it explicitly."""
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS application_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT NOT NULL UNIQUE,
                        operation TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        request_json TEXT NOT NULL,
                        response_json TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_application_records_created
                        ON application_records(created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_application_records_operation
                        ON application_records(operation, created_at DESC);

                    CREATE TABLE IF NOT EXISTS application_evaluations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        evaluation_id TEXT NOT NULL UNIQUE,
                        related_request_id TEXT,
                        operation TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        note TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_application_evaluations_created
                        ON application_evaluations(created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_application_evaluations_operation
                        ON application_evaluations(operation, created_at DESC);

                    CREATE TABLE IF NOT EXISTS application_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id TEXT,
                        event_name TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        details_json TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_application_events_created
                        ON application_events(created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_application_events_name
                        ON application_events(event_name, created_at DESC);
                    """
                )
        except (OSError, sqlite3.Error, PersistenceError) as error:
            if isinstance(error, PersistenceError):
                raise
            raise PersistenceError("Unable to initialize local application database") from error

    def _prune(self, connection: sqlite3.Connection, table: str, limit: int) -> None:
        connection.execute(
            f"DELETE FROM {table} WHERE id NOT IN (SELECT id FROM {table} ORDER BY id DESC LIMIT ?)",
            (limit,),
        )

    def record_interaction(
        self,
        *,
        request_id: str,
        operation: str,
        status: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
    ) -> None:
        if not request_id or not operation or not status:
            raise PersistenceError("request_id, operation, and status are required")
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO application_records
                        (request_id, operation, status, created_at, request_json, response_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        operation,
                        status,
                        utc_now(),
                        _canonical_json(request_payload),
                        _canonical_json(response_payload),
                    ),
                )
                self._prune(connection, "application_records", self.max_records)
        except sqlite3.IntegrityError as error:
            raise PersistenceError(f"Duplicate application request_id: {request_id}") from error
        except sqlite3.Error as error:
            raise PersistenceError("Unable to persist application interaction") from error

    def record_evaluation(
        self,
        *,
        evaluation_id: str,
        operation: str,
        outcome: str,
        related_request_id: str | None = None,
        note: str | None = None,
    ) -> None:
        if not evaluation_id or operation not in {"predict", "retrieve", "answer"}:
            raise PersistenceError("A valid evaluation_id and operation are required")
        if outcome not in {"pass", "fail", "needs_review"}:
            raise PersistenceError("A valid evaluation outcome is required")
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO application_evaluations
                        (evaluation_id, related_request_id, operation, outcome, created_at, note)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (evaluation_id, related_request_id, operation, outcome, utc_now(), note),
                )
                self._prune(connection, "application_evaluations", self.max_evaluations)
        except sqlite3.IntegrityError as error:
            raise PersistenceError(f"Duplicate application evaluation_id: {evaluation_id}") from error
        except sqlite3.Error as error:
            raise PersistenceError("Unable to persist application evaluation") from error

    def recent_evaluations(self, *, limit: int) -> list[dict[str, Any]]:
        if limit < 1:
            raise PersistenceError("evaluation history limit must be positive")
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT evaluation_id, related_request_id, operation, outcome, created_at, note
                    FROM application_evaluations
                    ORDER BY id DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError("Unable to read application evaluations") from error
        return [dict(row) for row in rows]

    def record_event(
        self,
        *,
        event_name: str,
        severity: str,
        details: dict[str, Any],
        request_id: str | None = None,
    ) -> None:
        if not event_name or severity not in {"info", "warning", "error"}:
            raise PersistenceError("A valid event name and severity are required")
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO application_events
                        (request_id, event_name, severity, created_at, details_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (request_id, event_name, severity, utc_now(), _canonical_json(details)),
                )
                self._prune(connection, "application_events", self.max_events)
        except sqlite3.Error as error:
            raise PersistenceError("Unable to persist application event") from error

    def recent_records(self, *, limit: int, operation: str | None = None) -> list[dict[str, Any]]:
        if limit < 1:
            raise PersistenceError("history limit must be positive")
        try:
            with self._connection() as connection:
                if operation:
                    rows = connection.execute(
                        """
                        SELECT request_id, operation, status, created_at, request_json, response_json
                        FROM application_records
                        WHERE operation = ?
                        ORDER BY id DESC LIMIT ?
                        """,
                        (operation, limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT request_id, operation, status, created_at, request_json, response_json
                        FROM application_records
                        ORDER BY id DESC LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError("Unable to read application history") from error
        return [
            {
                "request_id": row["request_id"],
                "operation": row["operation"],
                "status": row["status"],
                "created_at": row["created_at"],
                "request": json.loads(row["request_json"]),
                "response": json.loads(row["response_json"]),
            }
            for row in rows
        ]

    def counts(self) -> dict[str, int]:
        try:
            with self._connection() as connection:
                record_count = int(connection.execute("SELECT COUNT(*) FROM application_records").fetchone()[0])
                evaluation_count = int(
                    connection.execute("SELECT COUNT(*) FROM application_evaluations").fetchone()[0]
                )
                event_count = int(connection.execute("SELECT COUNT(*) FROM application_events").fetchone()[0])
        except sqlite3.Error as error:
            raise PersistenceError("Unable to count persisted application evidence") from error
        return {"records": record_count, "evaluations": evaluation_count, "events": event_count}

"""Controlled tests for bounded local SQLite persistence."""

from __future__ import annotations

import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance.application.persistence import PersistenceError, SQLiteStore


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(Path(self.temp.name) / "app.sqlite3", max_records=2, max_evaluations=2, max_events=3)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_initialization_creates_database(self):
        self.assertTrue(self.store.path.is_file())
        self.assertEqual(self.store.counts(), {"records": 0, "evaluations": 0, "events": 0})

    def test_interaction_round_trip(self):
        self.store.record_interaction(request_id="r1", operation="retrieve", status="retrieved", request_payload={"query": "air"}, response_payload={"result_count": 2})
        record = self.store.recent_records(limit=1)[0]
        self.assertEqual((record["request_id"], record["request"]["query"]), ("r1", "air"))

    def test_record_retention_is_bounded(self):
        for index in range(3):
            self.store.record_interaction(request_id=f"r{index}", operation="predict", status="scored", request_payload={}, response_payload={})
        self.assertEqual(self.store.counts()["records"], 2)
        self.assertEqual([row["request_id"] for row in self.store.recent_records(limit=10)], ["r2", "r1"])

    def test_event_retention_is_bounded(self):
        for index in range(5):
            self.store.record_event(event_name=f"event_{index}", severity="info", details={"i": index})
        self.assertEqual(self.store.counts()["events"], 3)

    def test_evaluation_retention_is_bounded_and_typed(self):
        for index in range(3):
            self.store.record_evaluation(
                evaluation_id=f"eval-{index}",
                operation="answer",
                outcome="needs_review" if index == 2 else "pass",
                note=f"note-{index}",
            )
        rows = self.store.recent_evaluations(limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["evaluation_id"], "eval-2")
        self.assertEqual(rows[0]["outcome"], "needs_review")

    def test_invalid_evaluation_outcome_is_rejected(self):
        with self.assertRaisesRegex(PersistenceError, "outcome"):
            self.store.record_evaluation(
                evaluation_id="eval", operation="answer", outcome="excellent"
            )

    def test_duplicate_request_id_is_rejected(self):
        self.store.record_interaction(request_id="same", operation="answer", status="answered", request_payload={}, response_payload={})
        with self.assertRaisesRegex(PersistenceError, "Duplicate"):
            self.store.record_interaction(request_id="same", operation="answer", status="answered", request_payload={}, response_payload={})

    def test_history_can_filter_operation(self):
        self.store.record_interaction(request_id="r1", operation="retrieve", status="retrieved", request_payload={}, response_payload={})
        self.store.record_interaction(request_id="r2", operation="answer", status="answered", request_payload={}, response_payload={})
        rows = self.store.recent_records(limit=10, operation="answer")
        self.assertEqual([row["request_id"] for row in rows], ["r2"])

    def test_connections_are_explicitly_closed(self):
        real_connect = sqlite3.connect
        created = []

        class TrackingConnection(sqlite3.Connection):
            def close(self):
                self.was_closed = True
                return super().close()

        def tracking_connect(*args, **kwargs):
            kwargs["factory"] = TrackingConnection
            connection = real_connect(*args, **kwargs)
            connection.was_closed = False
            created.append(connection)
            return connection

        with patch(
            "predictive_maintenance.application.persistence.sqlite3.connect",
            side_effect=tracking_connect,
        ):
            store = SQLiteStore(
                Path(self.temp.name) / "close_check.sqlite3",
                max_records=2,
                max_evaluations=2,
                max_events=2,
            )
            store.initialize()
            store.record_event(event_name="close_check", severity="info", details={})
            store.counts()

        self.assertGreaterEqual(len(created), 3)
        self.assertTrue(all(connection.was_closed for connection in created))



if __name__ == "__main__":
    unittest.main()

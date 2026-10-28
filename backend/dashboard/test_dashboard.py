"""Exercise aggregation and detail queries against isolated SQLite snapshots."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import dashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / "usage.sqlite3")
        self.patch = patch.object(dashboard, "DB", self.db)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        with sqlite3.connect(self.db) as c:
            c.execute(
                "CREATE TABLE events(event_id TEXT PRIMARY KEY, revision INT, day_utc TEXT, recording_count INT, duration_ms INT, source_words INT, source_chars INT, translated_words INT, translated_chars INT)"
            )
            c.executemany(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)",
                [(f"{i:08}", 1, "2026-10-27", 1, 1000, 4, 20, 2, 10) for i in range(51)]
                + [("fixture", 1, "2000-01-01", 1, 9000, 40, 200, 20, 100)],
            )

    def test_pagination_and_test_exclusion(self):
        first = dashboard.details(1)
        self.assertEqual(first["total"], 51)
        self.assertEqual(len(first["events"]), 50)
        self.assertEqual(len(dashboard.details(2)["events"]), 1)
        self.assertEqual(dashboard.details(3)["events"], [])
        self.assertTrue(all(e["day"] != "2000-01-01" for e in first["events"]))
        self.assertEqual(set(first["events"][0]), {"event_id", "day", "duration_ms", "source_chars", "source_words"})

    def test_latest_revision_and_totals(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE events SET revision=2,duration_ms=500,source_chars=10 WHERE event_id='00000000'")
        data = dashboard.summary()
        self.assertEqual(data["totals"]["recording_count"], 51)
        self.assertEqual(data["totals"]["duration_ms"], 50500)
        self.assertEqual(data["totals"]["source_chars"], 1010)
        self.assertEqual(data["test_days"][0]["recording_count"], 1)
        self.assertEqual(dashboard.details(1)["events"][0]["source_chars"], 10)

    def test_reads_do_not_modify_database(self):
        before = Path(self.db).read_bytes()
        dashboard.summary()
        dashboard.details(1)
        self.assertEqual(before, Path(self.db).read_bytes())


if __name__ == "__main__":
    unittest.main()

"""Numeric-only, opt-in cumulative outbox tests; all data and transport synthetic."""

import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import requests
import usage_sync as usage


class Response:
    def __init__(self, body, status=200, headers=None):
        self.body = json.dumps(body).encode()
        self.status_code = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_content(self, _):
        yield self.body


def acknowledge(_, **kwargs):
    return Response(
        {
            "schema_version": 1,
            "acknowledged": [{"event_id": e["event_id"], "revision": e["revision"]} for e in kwargs["json"]["events"]],
        }
    )


class UsageTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "metrics/queue.sqlite3"
        self.reporter = usage.UsageReporter(
            self.path, start_worker=False, endpoint="https://example.test/v1/usage/batch", upload_ready=True
        )

    def tearDown(self):
        self.reporter.close()
        self.temp.cleanup()

    def enable(self):
        self.reporter.configure(True, start_worker=False)
        self.reporter.capture_started("synthetic-local-lecture")

    def test_no_database_or_request_before_opt_in(self):
        self.reporter.capture_started("lecture")
        self.reporter.count_text("lecture", 1, "private sentinel")
        self.assertFalse(self.path.exists())
        with patch.object(requests.Session, "post") as post:
            self.assertFalse(self.reporter.sync_once())
            post.assert_not_called()

    def test_waiting_for_public_acceptance_never_contacts_private_endpoint(self):
        self.enable()
        self.reporter.upload_ready = False
        with patch.object(requests.Session, "post") as post:
            self.assertFalse(self.reporter.sync_once())
            post.assert_not_called()
        self.assertEqual(len(self.reporter.pending()), 1)

    def test_pause_resume_counts_once_and_excludes_paused_time(self):
        t = [100.0]
        with patch.object(usage.time, "monotonic", side_effect=lambda: t[0]):
            self.enable()
            t[0] = 105.0
            self.reporter.capture_stopped()
            t[0] = 130.0
            self.reporter.capture_started("synthetic-local-lecture")
            t[0] = 132.0
            self.reporter.capture_stopped()
        event = self.reporter.pending()[0]
        self.assertEqual(event["duration_ms"], 7000)
        self.assertEqual(event["recording_count"], 1)

    def test_numeric_counts_replace_partial_text_and_retranslations(self):
        self.enable()
        self.reporter.count_text("synthetic-local-lecture", 3, "A binary search tree")
        self.reporter.count_text("synthetic-local-lecture", 3, "Binary tree")
        self.reporter.count_text("synthetic-local-lecture", 3, "二叉树", translated=True)
        self.reporter.count_text("synthetic-local-lecture", 3, "二叉搜索树", translated=True)
        event = self.reporter.pending()[0]
        self.assertEqual(event["source_words"], 2)
        self.assertEqual(event["translated_chars"], 5)
        self.assertEqual(event["translated_words"], 0)
        self.assertEqual(set(event), {"event_id", "revision", "day_utc", *usage.FIELDS})
        self.reporter.capture_stopped()
        self.reporter.close()
        blob = b"".join(p.read_bytes() for p in self.path.parent.iterdir())
        for sentinel in ("binary search", "二叉搜索树"):
            self.assertNotIn(sentinel.encode(), blob)

    def test_network_failure_persists_across_restart_same_id_revision(self):
        self.enable()
        self.reporter.capture_stopped()
        original = self.reporter.pending()[0]

        def offline(*_, **__):
            raise requests.ConnectionError("synthetic offline")

        self.assertFalse(self.reporter.sync_once(offline))
        self.reporter.close()
        self.reporter = usage.UsageReporter(
            self.path,
            enabled=True,
            start_worker=False,
            endpoint="https://example.test/v1/usage/batch",
            upload_ready=True,
        )
        self.assertEqual(self.reporter.pending(), [original])
        self.assertTrue(self.reporter.sync_once(acknowledge))
        self.assertEqual(self.reporter.pending(), [])

    def test_lost_ack_reuses_snapshot_and_retries_idempotently(self):
        self.enable()
        self.reporter.capture_stopped()
        server, transmissions = {}, []

        def send(_, **kwargs):
            events = kwargs["json"]["events"]
            transmissions.append(events)
            for event in events:
                server[event["event_id"]] = event
            if len(transmissions) == 1:
                raise requests.ReadTimeout("acknowledgement lost")
            return acknowledge(_, **kwargs)

        self.assertFalse(self.reporter.sync_once(send))
        self.reporter.next_attempt = 0
        self.assertTrue(self.reporter.sync_once(send))
        self.assertEqual(transmissions[0], transmissions[1])
        self.assertEqual(sum(e["recording_count"] for e in server.values()), 1)

    def test_old_inflight_ack_does_not_clear_newer_local_revision(self):
        self.enable()

        def send(url, **kwargs):
            self.reporter.count_text("synthetic-local-lecture", 1, "new words")
            return acknowledge(url, **kwargs)

        self.assertTrue(self.reporter.sync_once(send))
        self.assertEqual(self.reporter.pending()[0]["source_words"], 2)

    def test_disable_while_uploading_clears_queue_and_late_ack_cannot_restore_it(self):
        self.enable()
        old_id = self.reporter.pending()[0]["event_id"]

        def send(url, **kwargs):
            self.reporter.configure(False, start_worker=False)
            return acknowledge(url, **kwargs)

        self.reporter.sync_once(send)
        self.assertEqual(self.reporter.pending(), [])
        self.reporter.configure(True, start_worker=False)
        self.reporter.capture_started("synthetic-local-lecture")
        self.assertNotEqual(self.reporter.pending()[0]["event_id"], old_id)
        self.assertEqual(self.reporter.pending()[0]["source_chars"], 0)

    def test_invalid_or_incomplete_ack_keeps_entire_batch(self):
        self.enable()
        original = self.reporter.pending()[0]
        for data in (
            {"schema_version": 1, "acknowledged": []},
            {"schema_version": True, "acknowledged": []},
            {"schema_version": 1, "acknowledged": [{"event_id": original["event_id"], "revision": True}]},
            {"schema_version": 1, "acknowledged": [{"event_id": original["event_id"], "revision": 0}]},
        ):
            self.reporter.next_attempt = 0
            self.assertFalse(self.reporter.sync_once(lambda *_, **__: Response(data)))
            self.assertEqual(self.reporter.pending()[0], original)

    def test_redirect_error_and_retry_after_never_acknowledge(self):
        self.enable()
        for status in (302, 400, 409, 429, 503):
            self.reporter.next_attempt = 0
            self.assertFalse(self.reporter.sync_once(lambda *_, **__: Response({}, status, {"Retry-After": "300"})))
            self.assertGreaterEqual(self.reporter.next_attempt - usage.time.monotonic(), 299)
            self.assertEqual(len(self.reporter.pending()), 1)

    def test_upload_whitelist_and_transport_does_not_follow_redirects_or_use_auth(self):
        self.enable()

        def send(url, **kwargs):
            self.assertEqual(url, "https://example.test/v1/usage/batch")
            self.assertFalse(kwargs["allow_redirects"])
            self.assertEqual(set(kwargs["json"]), {"schema_version", "events"})
            self.assertEqual(kwargs["headers"], {"X-Lecture-Usage-IP": "1"})
            return acknowledge(url, **kwargs)

        self.assertTrue(self.reporter.sync_once(send))
        for endpoint in (
            "http://example.test/v1/usage/batch",
            "https://user:pass@example.test/v1/usage/batch",
            "https://example.test/other",
            "https://example.test/v1/usage/batch?token=secret",
        ):
            self.assertFalse(usage.endpoint_allowed(endpoint))

    def test_server_higher_revision_allows_future_local_corrections(self):
        self.enable()
        ident = self.reporter.pending()[0]["event_id"]
        self.assertTrue(
            self.reporter.sync_once(
                lambda *_, **__: Response({"schema_version": 1, "acknowledged": [{"event_id": ident, "revision": 100}]})
            )
        )
        self.reporter.count_text("synthetic-local-lecture", 1, "a word")
        self.assertEqual(self.reporter.pending()[0]["revision"], 101)

    def test_database_failure_is_nonfatal_and_does_not_claim_persistence(self):
        self.reporter.path = self.path.parent / "unavailable/queue.sqlite3"
        with patch.object(Path, "mkdir", side_effect=PermissionError("synthetic read-only")):
            self.reporter.configure(True, start_worker=False)
        self.assertIn("暂不可写", self.reporter.state)

    def test_online_signal_retries_soon_but_honors_server_retry_after(self):
        self.enable()
        self.reporter.next_attempt = usage.time.monotonic() + 3600
        self.reporter.network_available()
        self.assertLess(self.reporter.next_attempt - usage.time.monotonic(), 6)
        self.reporter.next_attempt = 0
        self.reporter.sync_once(lambda *_, **__: Response({}, 429, {"Retry-After": "600"}))
        self.reporter.network_available()
        self.assertGreater(self.reporter.next_attempt - usage.time.monotonic(), 599)

    def test_blocked_upload_does_not_block_duration_checkpoints(self):
        import threading
        import time

        entered, release = threading.Event(), threading.Event()

        def blocked(url, **kwargs):
            entered.set()
            release.wait(5)
            return acknowledge(url, **kwargs)

        with patch.object(requests.Session, "post", side_effect=blocked):
            try:
                self.reporter.configure(True, start_worker=True)
                self.reporter.capture_started("synthetic-local-lecture")
                self.assertTrue(entered.wait(3))
                time.sleep(1.2)
                with self.reporter.lock:
                    duration = self.reporter._database().execute("SELECT duration_ms FROM events").fetchone()[0]
                self.assertGreaterEqual(duration, 1500)
            finally:
                release.set()
                self.reporter.close()

    def test_suspended_queue_survives_and_late_confirmation_is_ignored(self):
        self.enable()
        self.reporter.capture_stopped()
        event = self.reporter.pending()[0]

        def send(url, **kwargs):
            self.reporter.suspend()
            return acknowledge(url, **kwargs)

        self.reporter.sync_once(send)
        self.assertFalse(self.reporter.enabled)
        with self.reporter.lock:
            self.assertEqual(self.reporter._database().execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        self.reporter.configure(True, start_worker=False)
        self.assertEqual(self.reporter.pending(), [event])
        self.assertTrue(self.reporter.sync_once(acknowledge))
        self.assertEqual(self.reporter.pending(), [])


class EngineUsageTests(TestCase):
    def test_generation_consent_boundary_and_pause_share_one_event(self):
        import core
        from test_pipeline import Signals

        with tempfile.TemporaryDirectory() as folder, patch.object(core, "DATA_ROOT", Path(folder)):
            engine = core.Engine(Signals(), {"notes_interval": 3600})
            try:
                engine.ensure_session()
                engine.usage_reporter.configure(True, start_worker=False)
                engine.active = True
                engine.gen = 4
                engine.usage_capture_started(3)
                self.assertEqual(engine.usage_reporter.pending(), [])
                engine.usage_capture_started(4)
                engine.usage_min_paragraph = 5
                engine.count_usage_text(4, 4, "before consent")
                engine.count_usage_text(3, 5, "stale generation")
                self.assertEqual(engine.usage_reporter.pending()[0]["source_words"], 0)
                engine.count_usage_text(4, 5, "future words")
                self.assertEqual(engine.usage_reporter.pending()[0]["source_words"], 2)
                engine.stop()
                engine.usage_capture_started(4)
                self.assertFalse(engine.usage_capture_ready)
                engine.active = True
                engine.usage_capture_started(engine.gen)
                self.assertEqual(len(engine.usage_reporter.pending()), 1)
                engine.stop()
                engine.session_dir = None
                engine.ensure_session()
                engine.active = True
                engine.usage_capture_started(engine.gen)
                self.assertEqual(len(engine.usage_reporter.pending()), 2)
            finally:
                engine.stop()
                engine.close()

    def test_failed_capture_start_is_not_a_recording(self):
        import core
        from test_pipeline import Signals
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as folder, patch.object(core, "DATA_ROOT", Path(folder)):
            engine = core.Engine(
                Signals(), {"notes_interval": 3600, "stt_backend": "apple", "translation_backend": "apple"}
            )
            engine.notes_enabled = False
            engine.usage_reporter.configure(True, start_worker=False)
            stream = Mock()
            stream.start.side_effect = RuntimeError("synthetic permission denial")
            try:
                with (
                    patch.object(core.sd, "query_devices", return_value={"default_samplerate": 16000}),
                    patch.object(core.sd, "InputStream", return_value=stream),
                ):
                    engine.start(999)
                self.assertFalse(engine.active)
                self.assertEqual(engine.usage_reporter.pending(), [])
            finally:
                engine.close()

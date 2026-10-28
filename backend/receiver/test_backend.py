import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from app import App, Store, Limiter, Rejected, validate, MAX_BODY

E = {
    "event_id": "bd422b78-4478-4c05-9d10-b54e443f136a",
    "revision": 3,
    "day_utc": "2026-10-26",
    "recording_count": 1,
    "duration_ms": 125000,
    "source_words": 320,
    "source_chars": 1450,
    "translated_words": 18,
    "translated_chars": 760,
}


def raw(events=None):
    return json.dumps({"schema_version": 1, "events": events or [copy.deepcopy(E)]}).encode()


async def request(
    app, body, ct=b"application/json", path=b"/v1/usage/batch", peer="192.0.2.1", xff=None, ip_consent=False
):
    sent = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(m):
        sent.append(m)

    headers = [(b"content-type", ct)]
    if ip_consent:
        headers.append((b"x-lecture-usage-ip", b"1"))
    if xff:
        headers.append((b"x-forwarded-for", xff))
    await app(
        {
            "type": "http",
            "method": "POST",
            "path": path.decode(),
            "raw_path": path,
            "headers": headers,
            "client": (peer, 123),
            "http_version": "1.1",
        },
        receive,
        send,
    )
    return sent[0]["status"], dict(sent[0]["headers"]), json.loads(sent[1]["body"])


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name, reserve=0)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        with self.store.connect() as c:
            return c.execute("SELECT * FROM events ORDER BY event_id").fetchall()

    def test_ip_requires_consent_and_uses_trusted_source(self):
        app = App(self.store, trust_proxy=True)
        self.assertEqual(asyncio.run(request(app, raw()))[0], 200)
        with self.store.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM upload_sources").fetchone()[0], 0)
        for peer, forwarded, expected in [
            ("192.0.2.1", b"203.0.113.9", "192.0.2.1"),
            ("127.0.0.1", b"2001:db8::1", "2001:db8::1"),
        ]:
            self.assertEqual(asyncio.run(request(app, raw(), peer=peer, xff=forwarded, ip_consent=True))[0], 200)
            with self.store.connect() as c:
                self.assertEqual(
                    c.execute("SELECT source_ip FROM upload_sources ORDER BY id DESC LIMIT 1").fetchone()[0], expected
                )
        self.assertEqual(len(self.rows()), 1)
        with self.store.connect() as c:
            c.execute("INSERT INTO upload_sources(received_at, source_ip, event_ids) VALUES(0,'192.0.2.99','[]')")
        self.store.expire_sources()
        with self.store.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM upload_sources").fetchone()[0], 2)

    def test_retries_loss_order_correction_restart(self):
        for _ in range(10):
            self.store.commit(validate(raw()))
        self.assertEqual(len(self.rows()), 1)
        e = copy.deepcopy(E)
        e["revision"] = 2
        e["source_chars"] = 2000
        self.assertEqual(self.store.commit(validate(raw([e])))["acknowledged"][0]["revision"], 3)
        e["revision"] = 4
        e["source_chars"] = 1200
        # Ignore response to simulate response loss after committed write.
        self.store.commit(validate(raw([e])))
        self.store = Store(self.tmp.name, reserve=0)
        self.store.commit(validate(raw([e])))
        self.assertEqual(self.rows()[0][1], 4)
        self.assertEqual(self.rows()[0][6], 1200)

    def test_conflict_rolls_back_entire_batch(self):
        self.store.commit(validate(raw()))
        other = copy.deepcopy(E)
        other["event_id"] = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
        conflict = copy.deepcopy(E)
        conflict["duration_ms"] = 4
        with self.assertRaises(Rejected) as e:
            self.store.commit(validate(raw([other, conflict])))
        self.assertEqual(e.exception.status, 409)
        self.assertEqual(len(self.rows()), 1)

    def test_concurrent_duplicates(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(lambda _: self.store.commit(validate(raw())), range(50)))
        self.assertEqual(len(self.rows()), 1)
        with self.store.connect() as c:
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_validation(self):
        bad = []
        for k, v in [
            ("audio", "secret-audio"),
            ("text", "private-text"),
            ("api_key", "secret-key"),
            ("source_words", True),
            ("source_words", 1.0),
            ("duration_ms", -1),
            ("revision", 2**53),
            ("duration_ms", 604800001),
            ("source_chars", 100000001),
            ("day_utc", "2026-02-30"),
            ("event_id", "bad"),
        ]:
            e = copy.deepcopy(E)
            e[k] = v
            bad.append(raw([e]))
        bad += [
            raw([E, E]),
            b'{"schema_version":1,"schema_version":1,"events":[]}',
            raw().replace(b"125000", b"9" * 10000),
            b"null",
            raw().replace(b"125000", b"NaN"),
            raw().replace(b"125000", b"1e9"),
        ]
        for b in bad:
            with self.subTest(b=b[:10]):
                with self.assertRaises(Rejected):
                    validate(b)
        self.assertEqual(self.rows(), [])

    def test_atomic_invalid_batch(self):
        e = copy.deepcopy(E)
        e["text"] = "private"
        status, _, _ = asyncio.run(request(App(self.store), raw([E, e])))
        self.assertEqual(status, 400)
        self.assertEqual(self.rows(), [])

    def test_http_errors_and_routes(self):
        app = App(self.store)
        for body, ct, path, expected in [
            (b"x", b"text/plain", b"/v1/usage/batch", 415),
            (b" " * (MAX_BODY + 1), b"application/json", b"/v1/usage/batch", 413),
            (raw(), b"application/json", b"/v1/usage/batch/", 404),
            (raw(), b"application/json", b"/usage.sqlite3", 404),
            (raw(), b"application/json", b"/docs", 404),
        ]:
            self.assertEqual(asyncio.run(request(app, body, ct, path))[0], expected)

    def test_capacity_and_database_fault(self):
        self.store.quota = 1
        self.assertEqual(asyncio.run(request(App(self.store), raw()))[0], 503)
        self.store.quota = 1024**3
        with patch.object(self.store, "connect", side_effect=sqlite3.OperationalError("private/internal/path")):
            status, _, body = asyncio.run(request(App(self.store), raw()))
            self.assertEqual(status, 503)
            self.assertEqual(body, {"error": "unavailable"})
        self.assertEqual(self.rows(), [])

    def test_rate_limit_and_trust(self):
        app = App(self.store, Limiter(100, 1), trust_proxy=True)
        self.assertEqual(asyncio.run(request(app, raw(), xff=b"1.1.1.1"))[0], 200)
        status, headers, _ = asyncio.run(request(app, raw(), xff=b"2.2.2.2"))
        self.assertEqual(status, 429)
        self.assertEqual(headers[b"retry-after"], b"60")
        # Only loopback proxy can select different sources.
        self.assertEqual(asyncio.run(request(app, raw(), peer="127.0.0.1", xff=b"2.2.2.2"))[0], 200)
        limiter = Limiter(1, 100)
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("b"))
        limiter = Limiter(100000, 100000)
        for i in range(5000):
            limiter.allow(str(i))
        self.assertLessEqual(len(limiter.sources), 4096)

    def test_real_readonly_failure(self):
        def readonly():
            return sqlite3.connect(f"file:{self.store.path}?mode=ro", uri=True, isolation_level=None)

        with patch.object(self.store, "connect", side_effect=readonly):
            status, _, body = asyncio.run(request(App(self.store), raw()))
        self.assertEqual(status, 503)
        self.assertNotIn("acknowledged", body)
        self.assertEqual(self.rows(), [])

    def test_crashed_uncommitted_transaction(self):
        self.store.commit(validate(raw()))
        code = "import sqlite3,sys,os; c=sqlite3.connect(sys.argv[1],isolation_level=None); c.execute('BEGIN IMMEDIATE'); c.execute('UPDATE events SET revision=99'); os._exit(7)"
        result = subprocess.run([sys.executable, "-c", code, str(self.store.path)])
        self.assertEqual(result.returncode, 7)
        self.store = Store(self.tmp.name, reserve=0)
        self.assertEqual(self.rows()[0][1], 3)
        with self.store.connect() as c:
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_ip_expiry(self):
        limiter = Limiter()
        with patch("app.time.monotonic", return_value=100):
            limiter.allow("192.0.2.1")
        with patch("app.time.monotonic", return_value=161):
            limiter.prune()
        self.assertEqual(len(limiter.sources), 0)

    def test_uuid_case_same_identity(self):
        self.store.commit(validate(raw()))
        e = copy.deepcopy(E)
        e["event_id"] = e["event_id"].upper()
        self.store.commit(validate(raw([e])))
        self.assertEqual(len(self.rows()), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

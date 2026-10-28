"""Consented usage snapshots. Never log request data."""

import asyncio
from contextlib import closing
import datetime as dt
import ipaddress
import json
import os
import re
import shutil
import sqlite3
import time
from collections import OrderedDict
from pathlib import Path
from starlette.responses import JSONResponse

FIELDS = [
    "event_id",
    "revision",
    "day_utc",
    "recording_count",
    "duration_ms",
    "source_words",
    "source_chars",
    "translated_words",
    "translated_chars",
]
COUNTS = FIELDS[3:]
MAX_BODY = 128 * 1024
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z")


class Rejected(Exception):
    def __init__(self, status):
        self.status = status


def pairs(items):
    d = {}
    for k, v in items:
        if k in d:
            raise ValueError("duplicate")
        d[k] = v
    return d


def integer(s):
    if len(s) > 16:
        raise ValueError("integer")
    return int(s)


def invalid(_):
    raise ValueError("number")


def validate(raw):
    try:
        obj = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs, parse_int=integer, parse_float=invalid, parse_constant=invalid
        )
        if type(obj) is not dict or set(obj) != {"schema_version", "events"}:
            raise ValueError()
        if type(obj["schema_version"]) is not int or obj["schema_version"] != 1:
            raise ValueError()
        events = obj["events"]
        if type(events) is not list or not 1 <= len(events) <= 100:
            raise ValueError()
        seen = set()
        for e in events:
            if type(e) is not dict or set(e) != set(FIELDS):
                raise ValueError()
            eid = e["event_id"]
            if type(eid) is not str or not UUID.fullmatch(eid):
                raise ValueError()
            e["event_id"] = eid.lower()
            if e["event_id"] in seen:
                raise ValueError()
            seen.add(e["event_id"])
            day = e["day_utc"]
            if type(day) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day, re.ASCII):
                raise ValueError()
            if dt.date.fromisoformat(day).isoformat() != day:
                raise ValueError()
            for k in ["revision"] + COUNTS:
                limit = (
                    2**53 - 1
                    if k == "revision"
                    else 1
                    if k == "recording_count"
                    else 604800000
                    if k == "duration_ms"
                    else 100000000
                )
                if type(e[k]) is not int or not (1 if k == "revision" else 0) <= e[k] <= limit:
                    raise ValueError()
        return events
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        raise Rejected(400) from None


class Store:
    def __init__(self, directory, quota=1024**3, reserve=256 * 1024**2):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "usage.sqlite3"
        self.quota, self.reserve = quota, reserve
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute(
                "CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, day_utc TEXT NOT NULL, recording_count INTEGER NOT NULL, duration_ms INTEGER NOT NULL, source_words INTEGER NOT NULL, source_chars INTEGER NOT NULL, translated_words INTEGER NOT NULL, translated_chars INTEGER NOT NULL) WITHOUT ROWID"
            )

            c.execute(
                "CREATE TABLE IF NOT EXISTS upload_sources (id INTEGER PRIMARY KEY, received_at INTEGER NOT NULL, source_ip TEXT NOT NULL, event_ids TEXT NOT NULL)"
            )

    def expire_sources(self):
        with closing(self.connect()) as c:
            c.execute("DELETE FROM upload_sources WHERE received_at < ?", (int(time.time()) - 30 * 86400,))

    def connect(self):
        c = sqlite3.connect(self.path, timeout=2, isolation_level=None)
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA busy_timeout=2000")
        c.execute("PRAGMA journal_size_limit=16777216")
        c.execute("PRAGMA max_page_count=262144")
        return c

    def commit(self, events, source_ip=None):
        c = None
        try:
            size = sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file())
            # Reserve conservative growth for this transaction and WAL, never remove dedup keys.
            if size + 2 * MAX_BODY > self.quota or shutil.disk_usage(self.directory).free < self.reserve:
                raise Rejected(503)
            c = self.connect()
            c.execute("BEGIN IMMEDIATE")
            ack = []
            for e in events:
                vals = tuple(e[k] for k in FIELDS)
                row = c.execute("SELECT * FROM events WHERE event_id=?", (e["event_id"],)).fetchone()
                if row and row[1] == e["revision"] and row != vals:
                    raise Rejected(409)
                if row is None or e["revision"] > row[1]:
                    c.execute("INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?,?,?)", vals)
                ack.append({"event_id": e["event_id"], "revision": max(e["revision"], row[1] if row else 0)})
            if source_ip is not None:
                source_ip = str(ipaddress.ip_address(source_ip))
                now = int(time.time())
                c.execute("DELETE FROM upload_sources WHERE received_at < ?", (now - 30 * 86400,))
                c.execute(
                    "INSERT INTO upload_sources(received_at,source_ip,event_ids) VALUES(?,?,?)",
                    (now, source_ip, json.dumps([e["event_id"] for e in events])),
                )
            c.execute("COMMIT")
            return {"schema_version": 1, "acknowledged": ack}
        except (sqlite3.Error, OSError):
            raise Rejected(503) from None
        finally:
            if c is not None:
                if c.in_transaction:
                    c.rollback()
                c.close()


class Limiter:
    def __init__(self, global_limit=600, source_limit=60):
        self.global_limit, self.source_limit = global_limit, source_limit
        self.start = time.monotonic()
        self.total = 0
        self.sources = OrderedDict()

    def prune(self):
        now = time.monotonic()
        while self.sources and next(iter(self.sources.values()))[2] <= now - 60:
            self.sources.popitem(last=False)

    def allow(self, key):
        now = time.monotonic()
        if now - self.start >= 60:
            self.start = now
            self.total = 0
        if self.total >= self.global_limit:
            return False
        self.prune()
        self.total += 1
        old, count, _ = self.sources.get(key, (now, 0, now))
        if now - old >= 60:
            old, count = now, 0
        if key not in self.sources and len(self.sources) >= 4096:
            return False
        if count >= self.source_limit:
            return False
        self.sources[key] = (old, count + 1, now)
        self.sources.move_to_end(key)
        return True


class App:
    def __init__(self, store, limiter=None, trust_proxy=False):
        self.store = store
        self.limiter = limiter or Limiter()
        self.trust_proxy = trust_proxy
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            expiry_task = None

            async def expire_sources():
                while True:
                    await asyncio.sleep(5)
                    self.limiter.prune()
                    self.store.expire_sources()

            while True:
                msg = await receive()
                if msg["type"] == "lifespan.startup":
                    expiry_task = asyncio.create_task(expire_sources())
                    await send({"type": "lifespan.startup.complete"})
                else:
                    if expiry_task:
                        expiry_task.cancel()
                        try:
                            await expiry_task
                        except asyncio.CancelledError:
                            pass
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        elif scope["type"] != "http":
            return
        headers = scope.get("headers", [])
        peer = scope.get("client") or ("unknown", 0)
        key = peer[0]
        # Only trust the verified tailscaled HTTP proxy on loopback; never other peers.
        xff = [v for k, v in headers if k == b"x-forwarded-for"]
        if self.trust_proxy and peer[0] in ("127.0.0.1", "::1") and len(xff) == 1:
            try:
                key = str(ipaddress.ip_address(xff[0].decode("ascii")))
            except ValueError:
                pass
        response = None
        try:
            if not self.limiter.allow(key):
                raise Rejected(429)
            path = scope.get("raw_path", scope["path"].encode())
            if path == b"/healthz" and scope["method"] == "GET":
                response = JSONResponse({"status": "ok"})
            elif path != b"/v1/usage/batch" or scope["method"] != "POST":
                raise Rejected(404)
            else:
                cts = [v for k, v in headers if k == b"content-type"]
                if len(cts) != 1 or cts[0].split(b";")[0].strip().lower() != b"application/json":
                    raise Rejected(415)
                lengths = [v for k, v in headers if k == b"content-length"]
                if lengths:
                    try:
                        if len(lengths) != 1 or len(lengths[0]) > 8 or not lengths[0].isdigit():
                            raise ValueError()
                        if int(lengths[0]) > MAX_BODY:
                            raise Rejected(413)
                    except ValueError:
                        raise Rejected(400) from None
                if self.active >= 16:
                    raise Rejected(503)
                self.active += 1
                try:

                    async def body():
                        raw = bytearray()
                        while True:
                            m = await receive()
                            if m["type"] == "http.disconnect":
                                raise Rejected(400)
                            raw.extend(m.get("body", b""))
                            if len(raw) > MAX_BODY:
                                raise Rejected(413)
                            if not m.get("more_body"):
                                return bytes(raw)

                    try:
                        raw = await asyncio.wait_for(body(), 10)
                    except asyncio.TimeoutError:
                        raise Rejected(400) from None
                    events = validate(raw)
                    # One instance, one event-loop writer; no awaits within transaction.
                    ip_consent = [v for k, v in headers if k == b"x-lecture-usage-ip"] == [b"1"]
                    # Opt-in header is emitted only after accepting current rules.
                    # Never accept an IP supplied in the JSON or an untrusted proxy header.
                    source_ip = None
                    if ip_consent:
                        try:
                            source_ip = str(ipaddress.ip_address(key))
                        except ValueError:
                            pass
                    response = JSONResponse(self.store.commit(events, source_ip=source_ip))
                finally:
                    self.active -= 1
        except Rejected as e:
            response = JSONResponse(
                {
                    "error": {
                        400: "invalid_request",
                        404: "not_found",
                        409: "revision_conflict",
                        413: "too_large",
                        415: "unsupported_media_type",
                        429: "rate_limited",
                        503: "unavailable",
                    }[e.status]
                },
                status_code=e.status,
                headers={"Retry-After": "60"} if e.status in (429, 503) else None,
            )
        except Exception:
            response = JSONResponse({"error": "unavailable"}, status_code=503, headers={"Retry-After": "60"})
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        await response(scope, receive, send)


def create_app():
    return App(
        Store(os.environ.get("USAGE_DATA", "/var/lib/lecture-usage")),
        trust_proxy=os.environ.get("USAGE_TRUST_TAILSCALE") == "1",
    )

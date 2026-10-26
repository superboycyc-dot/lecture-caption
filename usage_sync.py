"""Opt-in numeric snapshots; no audio, text, credentials or device identifiers."""

import json
from functools import wraps
import random
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
import requests

# Release gate: enable only after independent, tailnet-external write verification.
PUBLIC_UPLOAD_READY = True
DEFAULT_USAGE_ENDPOINT = "https://orangepiaipro-us.taile2de37.ts.net/v1/usage/batch"
USAGE_NOTICE = "分享用量统计，帮助改进软件（可选）"
USAGE_DETAIL = "仅含录音次数、时长和转译词数/字数，不含录音、原文、译文或笔记。同意后联网同步至开发者后台，可随时关闭。"
FIELDS = ("recording_count", "duration_ms", "source_words", "source_chars", "translated_words", "translated_chars")
MAX_REVISION = 2**53 - 1


def lengths(text):
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", text)), sum(c.isalnum() for c in text)


def endpoint_allowed(endpoint):
    try:
        url = urlsplit(endpoint)
        return bool(
            url.scheme == "https"
            and url.hostname
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and url.path == "/v1/usage/batch"
            and url.port in (None, 443)
        )
    except ValueError:
        return False


def retry_after(value, now=None):
    try:
        if value.isascii() and value.isdigit():
            return min(86400, int(value[:10]))
        stamp = parsedate_to_datetime(value)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0, min(86400, stamp.timestamp() - (time.time() if now is None else now)))
    except (ValueError, TypeError, AttributeError, OverflowError):
        return 0


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate response key")
        result[key] = value
    return result


def statistics_only(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (sqlite3.Error, OSError):
            self.state = "本机统计暂不可写；不会影响录音"
            return None

    return guarded


class UsageReporter:
    def __init__(self, path, enabled=False, endpoint=None, upload_ready=None, start_worker=True):
        self.path = Path(path)
        self.enabled = bool(enabled)
        self.endpoint = DEFAULT_USAGE_ENDPOINT if endpoint is None else endpoint
        self.upload_ready = PUBLIC_UPLOAD_READY if upload_ready is None else upload_ready
        self.lock = threading.RLock()
        self.active = None
        self.epoch = 0
        self.closed = False
        self.db = None
        self.next_attempt = 0
        self.server_not_before = 0
        self.failures = 0
        self.state = "未开启"
        self.halt = threading.Event()
        self.worker = None
        self.upload_thread = None
        # No worker or DB for users who have never opted in.
        if self.enabled:
            self.configure(True, start_worker=start_worker)

    def _database(self):
        if self.db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.db = sqlite3.connect(self.path, check_same_thread=False)
            self.path.chmod(0o600)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("""CREATE TABLE IF NOT EXISTS events (
                local_key TEXT UNIQUE, event_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0, day_utc TEXT NOT NULL,
                recording_count INTEGER NOT NULL, duration_ms INTEGER NOT NULL,
                source_words INTEGER NOT NULL, source_chars INTEGER NOT NULL,
                translated_words INTEGER NOT NULL, translated_chars INTEGER NOT NULL)""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS parts (
                event_id TEXT, paragraph INTEGER, source_words INTEGER, source_chars INTEGER,
                translated_words INTEGER, translated_chars INTEGER, PRIMARY KEY(event_id, paragraph))""")
            self.db.commit()
        return self.db

    @statistics_only
    def configure(self, enabled, start_worker=True):
        with self.lock:
            if self.closed:
                return
            self.enabled = bool(enabled)
            self.epoch += 1
            if not self.enabled:
                self.active = None
                # Remove pending and retained snapshots, including after an app restart.
                if self.db is not None or self.path.exists():
                    db = self._database()
                    with db:
                        db.execute("DELETE FROM parts")
                        db.execute("DELETE FROM events")
                self.state = "未开启；本机待同步记录已清除"
                return
            self._database()
            self.next_attempt = max(time.monotonic(), self.server_not_before)
            self.failures = 0
            self.state = "后台尚未公网验收，仅在本机排队" if not self.upload_ready else "等待同步"
            if start_worker and self.worker is None:
                self.worker = threading.Thread(target=self._loop, daemon=True)
                self.worker.start()

    def _row(self, local_key):
        return (
            self._database()
            .execute("SELECT event_id,duration_ms FROM events WHERE local_key=?", (local_key,))
            .fetchone()
        )

    @statistics_only
    def capture_started(self, local_key):
        with self.lock:
            if not self.enabled or self.closed:
                return
            if self.active and self.active[0] == local_key:
                return
            self._checkpoint()
            db = self._database()
            row = self._row(local_key)
            if row is None:
                event_id = str(uuid.uuid4())
                with db:
                    db.execute(
                        "INSERT INTO events VALUES(?,?,1,0,?,1,0,0,0,0,0)",
                        (local_key, event_id, datetime.now(timezone.utc).date().isoformat()),
                    )
                row = (event_id, 0)
            self.active = (local_key, row[0], time.monotonic(), row[1])

    def _checkpoint(self):
        if self.active and self.enabled:
            _, event_id, started, base = self.active
            elapsed = min(604800000, base + max(0, int((time.monotonic() - started) * 1000)))
            with self._database() as db:
                db.execute(
                    """UPDATE events SET duration_ms=?, revision=MAX(revision,acknowledged)+1
                              WHERE event_id=? AND duration_ms<>?""",
                    (elapsed, event_id, elapsed),
                )

    @statistics_only
    def capture_stopped(self):
        with self.lock:
            self._checkpoint()
            self.active = None

    @statistics_only
    def count_text(self, local_key, paragraph, text, translated=False):
        # Only integer lengths survive this function; text is never stored/queued.
        with self.lock:
            if not self.enabled or self.closed:
                return
            words, chars = lengths(text)
            row = self._row(local_key)
            if row is None:
                return
            event_id = row[0]
            db = self._database()
            old = db.execute(
                "SELECT source_words,source_chars,translated_words,translated_chars FROM parts WHERE event_id=? AND paragraph=?",
                (event_id, paragraph),
            ).fetchone() or (0, 0, 0, 0)
            new = (*old[:2], words, chars) if translated else (words, chars, 0, 0)
            if new == old:
                return
            with db:
                db.execute("INSERT OR REPLACE INTO parts VALUES(?,?,?,?,?,?)", (event_id, paragraph, *new))
                sums = db.execute(
                    "SELECT COALESCE(SUM(source_words),0),COALESCE(SUM(source_chars),0),COALESCE(SUM(translated_words),0),COALESCE(SUM(translated_chars),0) FROM parts WHERE event_id=?",
                    (event_id,),
                ).fetchone()
                db.execute(
                    "UPDATE events SET source_words=?,source_chars=?,translated_words=?,translated_chars=?,revision=MAX(revision,acknowledged)+1 WHERE event_id=?",
                    (*sums, event_id),
                )

    def pending(self):
        with self.lock:
            if not self.enabled or self.closed:
                return []
            db = self._database()
            rows = db.execute(
                "SELECT event_id,revision,day_utc,"
                + ",".join(FIELDS)
                + " FROM events WHERE revision>acknowledged ORDER BY rowid LIMIT 100"
            ).fetchall()
            return [dict(zip(("event_id", "revision", "day_utc", *FIELDS), row)) for row in rows]

    def sync_once(self, transport=None):
        with self.lock:
            if not self.enabled or self.closed or not self.upload_ready or not endpoint_allowed(self.endpoint):
                return False
            if time.monotonic() < self.next_attempt:
                return False
            events = self.pending()
            if not events:
                self.next_attempt = time.monotonic() + 60
                self.state = "已同步"
                return True
            epoch, endpoint = self.epoch, self.endpoint
        delay = 0
        try:
            # Never reuse the speech client's credentials, cookies, proxy auth or netrc.
            with requests.Session() as session:
                session.trust_env = False
                session.headers.update({"User-Agent": "LectureCaption-Usage/1"})
                send = transport or session.post
                with send(
                    endpoint,
                    json={"schema_version": 1, "events": events},
                    timeout=(3, 5),
                    allow_redirects=False,
                    stream=True,
                ) as response:
                    delay = retry_after(response.headers.get("Retry-After"))
                    if response.status_code != 200:
                        raise ValueError("unacknowledged")
                    body = bytearray()
                    deadline = time.monotonic() + 12
                    for chunk in response.iter_content(1):
                        if time.monotonic() > deadline:
                            raise ValueError("response deadline exceeded")
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise ValueError("oversized response")
                    data = json.loads(body, object_pairs_hook=unique_object)
            expected = {event["event_id"]: event["revision"] for event in events}
            if (
                not isinstance(data, dict)
                or set(data) != {"schema_version", "acknowledged"}
                or type(data["schema_version"]) is not int
                or data["schema_version"] != 1
            ):
                raise ValueError("invalid acknowledgement")
            acks = data["acknowledged"]
            if not isinstance(acks, list) or len(acks) != len(events):
                raise ValueError("incomplete acknowledgement")
            accepted = {}
            for ack in acks:
                if not isinstance(ack, dict) or set(ack) != {"event_id", "revision"}:
                    raise ValueError("invalid acknowledgement")
                ident, revision = ack["event_id"], ack["revision"]
                if (
                    not isinstance(ident, str)
                    or ident in accepted
                    or ident not in expected
                    or type(revision) is not int
                    or not expected[ident] <= revision <= MAX_REVISION
                ):
                    raise ValueError("invalid acknowledgement")
                accepted[ident] = revision
            with self.lock:
                if self.enabled and not self.closed and epoch == self.epoch:
                    with self._database() as db:
                        for ident, revision in accepted.items():
                            db.execute(
                                "UPDATE events SET acknowledged=MAX(acknowledged,?) WHERE event_id=?", (revision, ident)
                            )
                    self.failures = 0
                    self.next_attempt = time.monotonic() + 60
                    self.state = "已同步；课堂继续时会累计更新"
            return True
        except (
            requests.RequestException,
            ValueError,
            TypeError,
            KeyError,
            OverflowError,
            RecursionError,
            sqlite3.Error,
        ):
            with self.lock:
                if self.enabled and not self.closed and epoch == self.epoch:
                    self.failures = min(self.failures + 1, 10)
                    self.server_not_before = time.monotonic() + delay
                    self.next_attempt = time.monotonic() + max(
                        delay, min(3600, 30 * 2 ** (self.failures - 1)) * random.uniform(1, 1.25)
                    )
                    self.state = "同步未确认，已保留本机记录，稍后自动重试"
            return False

    def suspend(self):
        """Hold a previously opted-in queue while new use rules await acceptance."""
        with self.lock:
            if self.closed:
                return
            self.capture_stopped()
            self.enabled = False
            self.epoch += 1
            self.state = "等待接受软件使用规则；未上传"

    def network_available(self):
        with self.lock:
            if self.enabled and not self.closed:
                self.next_attempt = max(self.server_not_before, time.monotonic() + random.uniform(1, 5))

    def _loop(self):
        while not self.halt.wait(1):
            try:
                with self.lock:
                    if self.closed:
                        return
                    self._checkpoint()
                    if (
                        self.enabled
                        and self.upload_ready
                        and endpoint_allowed(self.endpoint)
                        and time.monotonic() >= self.next_attempt
                        and (self.upload_thread is None or not self.upload_thread.is_alive())
                    ):
                        self.upload_thread = threading.Thread(target=self.sync_once, daemon=True)
                        self.upload_thread.start()
            except (sqlite3.Error, OSError):
                self.state = "本机统计暂不可写；不会影响录音"

    @statistics_only
    def close(self):
        with self.lock:
            self.capture_stopped()
            self.closed = True
            self.halt.set()
        if self.worker:
            self.worker.join(timeout=0.2)
        if self.upload_thread:
            self.upload_thread.join(timeout=0.2)
        # A delayed network response checks closed/epoch before touching this DB.
        with self.lock:
            if self.db is not None:
                self.db.close()
                self.db = None

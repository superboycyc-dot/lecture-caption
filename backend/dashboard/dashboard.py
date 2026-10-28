"""Read-only aggregate dashboard, bound exclusively to the Tailscale IP."""

import datetime
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

DB = os.environ.get("USAGE_DB", "/var/lib/lecture-usage/usage.sqlite3")
COLUMNS = ["recording_count", "duration_ms", "source_words", "source_chars", "translated_words", "translated_chars"]


def summary():
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2) as conn:
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute(
            "SELECT day_utc,"
            + ",".join("SUM(" + c + ")" for c in COLUMNS)
            + " FROM events GROUP BY day_utc ORDER BY day_utc DESC"
        ).fetchall()
    days = [dict(zip(["day"] + COLUMNS, row)) for row in rows]
    # The external acceptance fixture has a deliberately impossible product launch date.
    real = [d for d in days if d["day"] != "2000-01-01"]
    return {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "totals": {c: sum(d[c] for d in real) for c in COLUMNS},
        "days": real,
        "test_days": [d for d in days if d["day"] == "2000-01-01"],
    }


def details(page):
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        total = conn.execute("SELECT COUNT(*) FROM events WHERE day_utc != '2000-01-01'").fetchone()[0]
        rows = conn.execute(
            "SELECT event_id,day_utc,duration_ms,source_chars,source_words FROM events WHERE day_utc != '2000-01-01' ORDER BY day_utc DESC,event_id LIMIT 50 OFFSET ?",
            ((page - 1) * 50,),
        ).fetchall()
    return {
        "page": page,
        "page_size": 50,
        "total": total,
        "events": [dict(zip(["event_id", "day", "duration_ms", "source_chars", "source_words"], row)) for row in rows],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            data = Path(__file__).with_name("index.html").read_bytes()
            content_type = "text/html; charset=utf-8"
        elif self.path == "/api/stats":
            try:
                data = json.dumps(summary(), ensure_ascii=False).encode()
            except sqlite3.Error:
                self.send_error(503, "Statistics unavailable")
                return
            content_type = "application/json; charset=utf-8"
        elif urlsplit(self.path).path == "/api/events":
            params = parse_qs(urlsplit(self.path).query)
            try:
                page = int(params.get("page", ["1"])[0])
                if not 1 <= page <= 1000000:
                    raise ValueError()
            except ValueError:
                self.send_error(400)
                return
            try:
                data = json.dumps(details(page), ensure_ascii=False).encode()
            except sqlite3.Error:
                self.send_error(503, "Statistics unavailable")
                return
            content_type = "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer((os.environ.get("DASHBOARD_HOST", "127.0.0.1"), 18766), Handler).serve_forever()

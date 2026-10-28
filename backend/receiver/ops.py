"""Local SSH-only operations. No HTTP admin endpoint."""

import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

DATA = Path(os.environ.get("USAGE_DATA", "/var/lib/lecture-usage"))
BACKUP = Path(os.environ.get("USAGE_BACKUP", "/var/backups/lecture-usage"))
MAX_BACKUPS = 8 * 1024**3


def connect():
    return sqlite3.connect(f"file:{DATA / 'usage.sqlite3'}?mode=ro", uri=True)


def snapshot(c):
    return c.execute("SELECT * FROM events ORDER BY event_id").fetchall()


def monitor():
    db = sum(p.stat().st_size for p in DATA.iterdir() if p.is_file())
    backups = sum(p.stat().st_size for p in BACKUP.iterdir() if p.is_file())
    free = shutil.disk_usage(DATA).free
    print(
        json.dumps(
            {
                "state": "capacity_warning" if db > 800 * 1024**2 or backups > 6 * 1024**3 or free < 1024**3 else "ok",
                "database_bytes": db,
                "backup_bytes": backups,
                "free_bytes": free,
            }
        )
    )
    if db > 800 * 1024**2 or backups > 6 * 1024**3 or free < 1024**3:
        raise SystemExit(1)


def backup():
    BACKUP.mkdir(parents=True, exist_ok=True)
    current = sum(p.stat().st_size for p in BACKUP.iterdir() if p.is_file())
    dbsize = (DATA / "usage.sqlite3").stat().st_size
    if current + 3 * dbsize > MAX_BACKUPS or shutil.disk_usage(BACKUP).free < dbsize + 256 * 1024**2:
        print("backup_capacity_exceeded")
        raise SystemExit(1)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    tmp = BACKUP / (stamp + ".partial")
    target = BACKUP / (stamp + ".sqlite3")
    try:
        with connect() as src, sqlite3.connect(tmp) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError()
        # Restore to a separate database and compare every committed snapshot.
        with tempfile.TemporaryDirectory(dir=BACKUP) as d:
            with sqlite3.connect(tmp) as src, sqlite3.connect(Path(d) / "restored.sqlite3") as restored:
                src.backup(restored)
                if restored.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or snapshot(src) != snapshot(
                    restored
                ):
                    raise RuntimeError()
        with tmp.open("rb") as f:
            os.fsync(f.fileno())
        tmp.replace(target)
        fd = os.open(BACKUP, os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
        for old in sorted(BACKUP.glob("*.sqlite3"))[:-7]:
            old.unlink()
        print("backup_and_restore_verified")
    except Exception:
        tmp.unlink(missing_ok=True)
        print("backup_failed")
        raise SystemExit(1) from None


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "query"
    if action == "query":
        print("未经身份验证的产品用量估计；不是独立用户统计，不能用于计费")
        cols = [
            "day_utc",
            "recording_count",
            "duration_ms",
            "source_words",
            "source_chars",
            "translated_words",
            "translated_chars",
        ]
        with connect() as c:
            for row in c.execute(
                "SELECT day_utc,SUM(recording_count),SUM(duration_ms),SUM(source_words),SUM(source_chars),SUM(translated_words),SUM(translated_chars) FROM events GROUP BY day_utc ORDER BY day_utc"
            ):
                print(json.dumps(dict(zip(cols, row)), ensure_ascii=False))
    elif action == "backup":
        backup()
    elif action == "monitor":
        monitor()
    else:
        raise SystemExit("unknown_operation")

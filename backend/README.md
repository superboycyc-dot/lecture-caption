# Usage backend 1.0.0

Versioned source for the opt-in numeric usage receiver and private dashboard. Client application versions are independent; this source publication does not replace any macOS release asset.

- `receiver/`: ASGI ingestion, strict schemas, revision-based idempotency, bounded request/rate limits, SQLite persistence, backup/restore verification and capacity timers.
- `dashboard/`: standard-library HTTP dashboard with daily totals and paginated per-recording details. It does not identify computers, record IPs, or expose transcript/audio content.
- Dependencies are pinned in `receiver/requirements-lock.txt`. Dashboard uses Python's standard library only.
- Supported receiver runtime: Python 3.10+ on Linux; CI checks Python 3.10 and 3.13.

## Local verification

```sh
python3 -m venv /tmp/lecture-backend-venv
/tmp/lecture-backend-venv/bin/pip install -r backend/receiver/requirements-lock.txt
/tmp/lecture-backend-venv/bin/python -m unittest discover -s backend/receiver -p 'test_*.py' -v
/tmp/lecture-backend-venv/bin/python -m unittest discover -s backend/dashboard -p 'test_*.py' -v
ruff check backend
ruff format --check backend
```

All automated backend tests use isolated, fictional data. They do not contact the deployed endpoint. The separately dispatched public acceptance workflow is opt-in and must only submit fictional fixtures.

## Deployment and boundaries

See [receiver deployment](receiver/README.md) and [dashboard deployment](dashboard/README.md). No database, real usage snapshots, host credentials, SSH configuration, raw job/access logs, device audit or wheel binaries belong in Git. Existing public acceptance evidence is already documented under `docs/deployment/`.

The receiver is unauthenticated numeric self-reporting; counters are estimates, not verified unique users or billable metering. Date grouping is UTC. A random event ID identifies a recording, never a device. Older revisions do not overwrite newer snapshots; equal-revision conflicting batches fail atomically. Public transport may process IP diagnostics; the application disables access logs and does not persist source IPs.

The dashboard must stay on loopback or a Tailscale interface. Do not add it to Funnel. Tailnet members allowed to connect to that port can read its statistics; there is no additional login. SQL uses `mode=ro` and `query_only`, while WAL shared-memory maintenance requires directory write access at the OS level. It is not an OS-enforced read-only database sandbox.

## Change and release policy

Use a focused PR, green client and backend CI, and review deployment changes before applying them. This version imports the already deployed receiver/dashboard; production data and network configuration are unchanged by merging source. Backend source releases may use a distinct `backend-vX.Y.Z` tag after merge. Never reuse a client `vX.Y.Z` tag or overwrite published assets. Record the deployed commit when performing the next server deployment; keep the previous code directory and database backups for rollback.

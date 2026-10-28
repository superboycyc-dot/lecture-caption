# Receiver deployment

Run `sudo sh deploy.sh RELEASE_NAME` from this directory on the inspected Ubuntu host. It creates an isolated release and venv, checks pinned dependencies and unit tests, backs up an existing database, changes the `current` symlink and restarts only `lecture-usage.service`. Never run it against an unknown host without checking its Python version, available memory/disk, service names and port ownership. It does not upgrade the OS or configure Funnel/SSH/firewalls.

Default storage: `/var/lib/lecture-usage/usage.sqlite3`; listener: `127.0.0.1:18765`; dedicated `lecture-usage` service user. Only the ingest/health endpoint should be proxied publicly. Schema and example JSON files contain fictional data. The `USAGE_TRUST_TAILSCALE=1` service setting assumes only the local Tailscale proxy reaches this loopback listener; do not expose it directly to arbitrary reverse proxies without reviewing source identity handling.

For an offline install, provide a separately verified `wheelhouse/` with `SHA256SUMS` covering the locked wheels. Binary dependencies are not versioned in this repository. Otherwise installation uses the pinned versions from PyPI.

After deploy verify `/healthz`, a fictional acknowledged upload, conflict/duplicate semantics, service restart persistence and independent external HTTPS access. Do not submit private recordings or credentials as test content. Public acceptance can be run through the repository workflow after explicitly reviewing the destination.

Backups: daily at 04:15 UTC, seven retained; each backup is restored into a temporary database and compared. Capacity monitoring is hourly. Operators should monitor systemd failures; timers alone do not send remote alerts. Data retention is intentionally not auto-expired, because removing event IDs can allow old cumulative snapshots to be counted again.

Rollback code: record the old `readlink /opt/lecture-usage/current`, stop only the receiver, restore the previous release symlink and start it again. Do not restore an old database just to roll back code: doing so loses subsequent acknowledged writes. Verify schema compatibility before a future migration; this release has no schema migration.

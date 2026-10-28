# Private dashboard deployment

Install `dashboard.py` and `index.html` into `/opt/lecture-usage-dashboard/` with root ownership and mode 0644, and install the supplied unit into `/etc/systemd/system/`. The receiver's `lecture-usage` user must already exist. No pip packages are required.

Create a root-owned mode-0600 `/etc/lecture-usage-dashboard.env` containing `DASHBOARD_HOST=YOUR_TAILSCALE_IPV4`. Use only the host's Tailscale address; the program defaults safely to loopback when no value is supplied. Check port 18766 is free, then run `systemctl daemon-reload` and `systemctl enable --now lecture-usage-dashboard`. Visit `http://YOUR_TAILSCALE_IPV4:18766/` from an authorized tailnet device. Do not expose this port through Funnel, router forwarding or a public bind address.

The dashboard displays aggregate counts, UTC daily totals and 50-record pages of recording ID/date/duration/source characters/source words. Same-day ID ordering is stable but not chronological: no exact recording timestamp is collected. Every recording shows its latest cumulative snapshot, not every HTTP upload. The fictional acceptance day `2000-01-01` is excluded from production tables and shown separately as test data. This explicit convention must be revisited if legitimate historical usage imports are ever supported.

Browser refreshes every 60 seconds. No third-party scripts/fonts, cookies, device ID, IP persistence, write routes or access logs. WAL shared-memory support needs OS directory write permission, although all query connections use `mode=ro` and `query_only=ON`. The service unit makes that exception explicit. Never claim it is an OS-enforced read-only principal.

For a custom `USAGE_DB` path, update both the environment and systemd filesystem policy. Keep a copy of the previous code directory before deploying. Roll back those two source files and restart only `lecture-usage-dashboard`; stopping/disabling the dashboard does not affect ingestion. Test `/`, `/api/stats`, `/api/events?page=1`, invalid page 400 and unknown path 404 after updating.

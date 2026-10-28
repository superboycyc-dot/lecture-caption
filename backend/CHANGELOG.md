# Unreleased

- Add opt-in connection IP receipts linked to upload event IDs, trusted proxy validation, 30-day expiry and IP-free backups. Existing numeric event schema and acknowledgements are unchanged.

# Backend changelog

## 1.0.0 — 2026-10-27

- Import the deployed strict numeric receiver, revision deduplication, backup/restore and capacity operations into the product repository.
- Version the private dashboard with UTC daily aggregates and paginated per-recording details; exclude fictional acceptance records.
- Add configurable private bind address, deployment/rollback documentation and Python 3.10/3.13 CI.
- No client version, collection schema, existing production data or published app asset changes.

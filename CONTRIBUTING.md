# Contributing

Use Issues for bugs and scoped feature proposals. Include macOS/chip, release version, input type, steps, expected vs actual behavior and sanitized error messages. Do not attach keys, private recordings or class notes.

1. Fork and create a branch from `main`.
2. Follow README's developer setup on Apple Silicon / Python 3.13.
3. Keep capture, API and notes behavior explicit; preserve quota safeguards and source-text durability.
4. Run Ruff, unit tests, release checks, and `python scripts/build_app.py` for packaging changes.
5. For UI changes attach a synthetic-data screenshot. For a bug fix add a meaningful regression test.
6. Open a PR describing the problem, change, checks and remaining limits. CI must pass before merge.

Use focused commits and update the changelog for user-visible changes. Third-party code requires compatible licensing, version provenance and retained notices. Do not add telemetry, paid-provider fallback, persistent plaintext credentials, or automatic upload before Start.

Contributions are submitted under the project's MIT license unless a separate retained upstream license applies. Review `SECURITY.md` for vulnerability reporting and `docs/RELEASING.md` for releases.

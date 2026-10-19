# Maintenance

Repository owner: **@superboycyc-dot**. Codex assists with code, tests, issues, PRs, releases and documentation when asked or through an explicitly configured automation. It is not the legal repository owner and does not run continuously merely because this file exists.

## Automated by GitHub

- CI on main and PRs: lint, tests, release-input checks, Mac build and isolated UI smoke test.
- Weekly dependency-update PRs, with a limited queue. No automatic merging.
- Tag-triggered release builds and versioned assets/checksums.
- Main branch protections and security features, when supported and successfully enabled.

## Assisted maintenance workflow

1. Triage against the exact release and a redacted reproduction.
2. Implement on a branch, preserve privacy, add regression coverage.
3. Open a PR and wait for required CI.
4. Merge verified changes; update version/changelog and ship an immutable version when appropriate.
5. Download/verify published assets and record remaining manual-device limitations.

Human participation is needed for login/authorization, private real-world audio tests, optional Apple Developer signing, new costs or scope changes. No guarantee is made that local Codex work can continue while its execution Mac is asleep. Background issue monitoring is not enabled by this release; it requires an explicitly configured schedule/runtime.

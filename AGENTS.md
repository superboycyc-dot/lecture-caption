# Repository maintenance

This repository is maintained with Codex assistance. The human GitHub account owner retains ownership and final control. These instructions do not create autonomous background work.

- Never inspect, commit, upload or print real API keys, Keychain contents, private recordings, personal notes, app logs or user config.
- Keep `.env`, `config.json`, `sessions/`, `logs/`, native build outputs and application bundles out of Git. Distribute release binaries as release assets, not commits.
- Use `docs/PRIVACY.md` as the behavioral contract. Do not collect usage without explicit opt-in. Keep usage numeric-only, honor opt-out, and leave the public-upload gate disabled until independent public acceptance. Do not add implicit paid API fallback or capture before explicit Start.
- Preserve upstream licenses and provenance in `vendor/`; avoid incidental reformatting there.
- Work on a focused branch, add relevant regression tests, run the documented checks, open a PR and wait for CI. Do not force-push or delete protected branches.
- Do not merge failing checks or claim live provider/device testing from mocks.
- Update user docs, changelog and version together when shipping a user-visible change.
- Follow `docs/RELEASING.md`: source commit, tagged build, checksums, release assets, verification. Never silently replace published assets for an existing tag; release a new patch version.
- Do not read or modify synchronized ChatGPT `sources/` mirrors. Work in this Git repository.

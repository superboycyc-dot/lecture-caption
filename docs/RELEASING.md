# Release process

1. Work on a branch and merge a reviewed, green PR. Update `pyproject.toml`, changelog, user docs and `docs/releases/vX.Y.Z.md` together.
2. Run Ruff, unit tests and `python scripts/check_release.py`; verify the working tree contains no local user data.
3. On Apple Silicon, install the pinned dependencies, run `python scripts/collect_licenses.py`, and `python scripts/build_app.py`.
4. Smoke-test the built bundle with a dummy key and isolated data directory. Test real microphone/system audio and APIs manually only with authorized test content and your own credential; record what was actually tested.
5. Tag the exact source commit: `git tag -a vX.Y.Z -m "Lecture Caption vX.Y.Z"`, then push it. The tag must match `pyproject.toml` and an existing release-notes file.
6. The Release workflow rebuilds from that commit, packages the independent app and `git archive` source, computes SHA-256 sums and publishes the assets. It uses `GITHUB_TOKEN` only; no speech API key or signing certificate is needed.
7. Inspect Actions, download the published ZIP, verify the sums, inspect that the bundle contains no personal data, and launch the published app. Confirm release links and notices.

If cloud CI is unavailable, perform these same steps locally and use `gh release create` against the verified tag, explicitly documenting local verification. Do not silently overwrite assets for a published version; ship a new patch version for corrections.

## Third-party notices and replaceable libraries

The app is MIT; dynamic Qt/PySide and other runtime components retain their licenses. `scripts/collect_licenses.py` retains the exact installed notices in `licenses/`, which are included in both source and binary releases. Source/build inputs are published with each release.

The bundle uses dynamically loaded, replaceable Qt frameworks rather than statically linking Qt into proprietary code. No reverse-engineering restrictions or library integrity lock are imposed. To use a compatible modified Qt/PySide, build it, install it into the build environment in place of the pinned wheel, run the same build script, and ad-hoc sign the resulting application. Preserve its licensing terms and updated source provenance.

Official corresponding source repositories: [PySide/Shiboken](https://code.qt.io/pyside/pyside-setup.git/) and [Qt base](https://code.qt.io/qt/qtbase.git/), with matching release tags. See [Qt LGPL documentation](https://doc.qt.io/qt-6/lgpl.html). If a future release modifies these libraries, its modifications and the exact corresponding source must be published too.

## Signing

Versions through 2.4.4 remain ad-hoc signed. Starting with 2.4.5, official assets require Developer ID Application signing and accepted Apple notarization, stapling and Gatekeeper validation. See DEVELOPER_ID.md. The tagged workflow validates source/build but intentionally does not publish its ad-hoc CI artifact; the verified notarized maintainer build is published against the same tag. Never commit certificates, provisioning secrets or Apple credentials.

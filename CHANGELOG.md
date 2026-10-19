# Changelog

## 0.3.0 — 2026-10-19

First public source release of the existing macOS application.

- Microphone and native ScreenCaptureKit system-audio inputs.
- English/Chinese floating captions and incremental CS/math Markdown notes.
- Blue-and-white icon and UI, independent Pin and opacity controls.
- macOS Keychain save/load/delete for API credentials.
- Independent Apple Silicon application bundle, local app-data directory.
- Source builds, automated tests/builds, release checksums, provenance and notices.

Known limitations: chunked latency; one input and shared credential at a time; pause drops untranscribed audio; no LaTeX rendering in the built-in reader; no Developer ID notarization; broad device and long-session validation remains pending.

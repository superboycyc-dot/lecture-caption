# Changelog

## 0.4.0 — 2026-10-21

- One resizable workspace: notes left, bilingual transcript right; settings open on demand.
- Persistent caption cards, current-segment highlighting, animated follow, pause-follow while reading history. Last 300 cards remain in memory; full transcript stays on disk.
- Dedicated Start/Stop, input selector, live audio meter and labeled local speech-API usage on the main window.
- Optional Apple on-device English speech recognition (experimental) and Apple English-to-Chinese translation (macOS 15+, installed language packs). No implicit cloud fallback.
- Pure local captions need no API key when automatic notes are disabled. Structured notes continue to use Groq.
- Persist presentation/backend preferences without storing credentials in config.


## 0.3.0 — 2026-10-19

First public source release of the existing macOS application.

- Microphone and native ScreenCaptureKit system-audio inputs.
- English/Chinese floating captions and incremental CS/math Markdown notes.
- Blue-and-white icon and UI, independent Pin and opacity controls.
- macOS Keychain save/load/delete for API credentials.
- Independent Apple Silicon application bundle, local app-data directory.
- Source builds, automated tests/builds, release checksums, provenance and notices.

Known limitations: chunked latency; one input and shared credential at a time; pause drops untranscribed audio; no LaTeX rendering in the built-in reader; no Developer ID notarization; broad device and long-session validation remains pending.

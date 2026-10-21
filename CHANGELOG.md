# Changelog

## 2.0.0 — 2026-10-21

- Use a pure white background throughout the notes pane, including the empty placeholder.

- Enable generation-safe live input/recognition switching and epoch-safe translation-only switching without restarting capture.
- Rewrite coherent notes from a cumulative source document plus prior notes; persist transcript.md with in-place paragraph revisions.
- Add green/grey/error audio indicator and compact allowance/request counters; remove processing-time and duration clutter.
- Make return-to-latest a small viewport overlay that auto-hides at the bottom without shrinking content.

- Replace audio-chunk cards with borderless timestamped paragraphs, black source/blue translation on a light reading surface, and live current-paragraph emphasis.
- Share cumulative utterance recognition and full-paragraph retranslation across Apple/Groq, revising the same paragraph until a natural pause (bounded at 24s). Preserve latest drafts on pause and queue each completed source for notes once.

- Fix Apple local recognition on macOS 26 using SpeechAnalyzer instead of legacy dictation; add explicit in-app model preparation, compatible audio conversion and sanitized error codes. Verified with generated CS speech and Apple translation.

- Move CI/release builds to supported macOS 26 runners; macOS 14 runner images retire November 2, 2026.

- One resizable workspace: notes left, bilingual transcript right; settings open on demand.
- Persistent caption cards, current-segment highlighting, animated follow, pause-follow while reading history. Last 300 cards remain in memory; full transcript stays on disk.
- Compact single-row toolbar with source, recognition/translation backends, English/Chinese/bilingual display, Start/Pause, Stop and a settings icon. Audio meter and usage are at the bottom; the pin control is removed.
- Note placeholder hints disappear after first content. Refresh/folder icons sit inside the note pane; Markdown source is available from its context menu.
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

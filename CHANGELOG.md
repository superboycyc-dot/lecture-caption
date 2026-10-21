# Changelog

## 2.3.0 — local preview, unreleased

- Replace the highlight text button with an original H / yellow marker icon. Left-align note menu actions and use “立即整理”.
- Replace the Customize checkbox/frame with a collapsed “高级设置” disclosure. Enable automatic updates by default, preserving subsequent explicit opt-out.
- Make first-run setup Groq-first, preparing Apple backup resources in the same flow; only explicit Skip selects local captions with notes disabled. Apple preparation failure does not block Groq setup.
- Replace the final text tutorial with an input-blocking grey spotlight overlay, white arrows to actual controls, step counters, Next and Skip. Never activate capture from the tour.
- Bind deferred caption/key-load timers to their widgets to prevent callbacks after window disposal.

## 2.2.0 — local preview, unreleased

- Add short first-run teaching, source choice, one-action Apple setup and official Groq registration/key onboarding. Validate/save keys and prepare permissions in one flow, without capture.
- Collapse detailed settings behind Customize; retain defaults and offer setup again from Settings/About.
- Edit notes inline with title/format toolbar and a three-item ellipsis menu. Add Markdown input, source view, ==highlight==, Command shortcuts, lists/headings and debounced backup. Defer AI during editing and reject stale results.
- End chooses Markdown or PDF before the destination picker. Retain highlighted text in Markdown/PDF and keep original session backups. Note-only documents can also End/export without microphone capture or an API key.
- Use a main-process native microphone-permission bridge; prepare system audio separately without starting a stream. Add an embedded WKWebView for official Groq pages, with an external-browser fallback.
- Stop idle audio workers at shutdown and dispose GUI documents before Qt teardown.


## 2.1.0 — local preview, unreleased

- Import UTF-8 Markdown as a continuation baseline; edit notes with snapshots and reject stale model overwrites.
- End waits for final notes/revision then opens Save As, remembers the export directory and retains internal backups.
- Automatically reorganize whole notes and generate a topic title every 1–5 minutes (default 3); no manual revise action.
- Click the logo for version, Yichen Chen developer/contact information, repository and update links. Official-release checking/download defaults on, with checksum/bundle validation, idle installation and macOS permission handling.


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

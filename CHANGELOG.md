# Changelog

## 3.1.0 — 2026-10-27
- Record consented usage-upload connection IPs on the receiver; update rules and require renewed agreement.
- Add an in-app recent-notes chooser with titles, modification times and 15-character previews.
- Show “打开历史” in the empty notes pane; preserve historical originals when continuing or editing.


## 3.0.0 — 2026-10-27
- Launch the 3.0.0 stable distribution with a drag-to-Applications DMG, bilingual installation instructions and a consistent Finder window layout.
- Sign, notarize and staple both the application and the DMG; retain the signed app ZIP for existing in-app updaters.
- Rewrite the GitHub home page around the app’s features, installation, model choices and data handling; keep detailed Chinese and English guides.
- Preserve 2.4.6 note generation, provider recovery, transcript export and user data.


## 2.4.6 — 2026-10-27
- Append new notes every 30 seconds and consolidate the whole document every five minutes.
- Keep safe, specific Groq note failure reasons visible until successful recovery, preserving pending source on failure.
- Bound incremental note context/output, drain failure backlogs in batches and scale consolidation output to document size.
- Retry network/timeouts, 429 and temporary server errors at most twice with backoff, per-model cooldowns and cancellation on capture stop.
- Save transcript Markdown in the default PDF directory and add a separate transcript export button.

## 2.4.5 — 2026-10-26
- Distribute official macOS assets with Developer ID Application signing, Hardened Runtime, secure timestamps and an accepted stapled Apple notarization ticket.
- Keep signing identities and notarization authorization in the local Keychain; prevent unsigned CI artifacts being published as official releases.
- Require matching Developer ID team and notarization validation for updates from an already Developer ID-signed installation.

## 2.4.4 — 2026-10-26
- Resolve the original bundle path under macOS App Translocation before deciding whether installation is needed or launching an update.
- Skip the installation prompt for Applications subfolders/renamed apps, and add a one-launch handoff guard to prevent reopening loops if path resolution is unavailable.

## 2.4.3 — 2026-10-26
- Offer one-click installation into Applications on first launch from Downloads, before setup, capture or update workers start. Validate the copy and reopen it; preserve original files and never overwrite an existing installation.
- Existing installations can be opened directly for normal updates. Cancellation/failure allows continued use, with a manual-install fallback.

## 2.4.2 — 2026-10-26
- Show disabled automatic notes and note-provider failures clearly; prevent editor focus from indefinitely blocking automatic notes. Actual edits resume after saving and an idle interval.
- Automatically save PDF to Desktop or a configured directory after finishing, retain internal Markdown, and offer Save As MD/PDF or Done.
- Add offline math rendering, formula editing and lossless Markdown/PDF export for supported TeX math syntax.
- Add prominent first-launch warning before downloads and explicit Groq key-name/expiration/copy instructions in both setup windows.
- Keep Apple speech and translation preparation independent; expose download controls and a post-Groq backup reminder/retry.

## 2.4.1 — 2026-10-26

- Move a compact “同意《软件使用规则》” checkbox/link above first-run connection buttons; require acceptance before setup/capture, and show it only on the first page.
- Add an in-app rules dialog covering audio processing, permissions, numeric usage, offline retries, credentials, updates and licenses. Explicitly disclose numeric sharing in the single required first-run agreement and retain the Settings opt-out.
- Persist accepted rules version; hold a previously opted-in outbox until the new rules are accepted. Existing notes can still be read/exported without accepting.

## 2.4.0 — 2026-10-26

- Add optional numeric usage consent alongside first-run permission setup and in Settings, without an extra permission step. Default off; disabling clears the local queue.
- Persist cumulative per-lecture numeric snapshots with revision-based acknowledgements, offline retry, backoff and no content/device identifiers. Count pause/resume once and replace interim paragraph counts.
- Enable the verified public HTTPS receiver after independent GitHub-hosted acceptance of revision handling, retries, restricted routes and rate limits. Sharing remains off until explicit consent; ordinary users do not need Tailscale.

## 2.3.0 — 2026-10-21

- Update certifi to 2026.10.19, removing compromised emSign trust roots (GHSA-6q48-6c7w-9gw2).

- Replace the highlight text button with an original H / yellow marker icon. Left-align note menu actions and use “立即整理”.
- Replace the Customize checkbox/frame with a collapsed “高级设置” disclosure. Enable automatic updates by default, preserving subsequent explicit opt-out.
- Make first-run setup Groq-first, preparing Apple backup resources in the same flow; only explicit Skip selects local captions with notes disabled. Apple preparation failure does not block Groq setup.
- Replace the final text tutorial with an input-blocking grey spotlight overlay, white arrows to actual controls, step counters, Next and Skip. Never activate capture from the tour.
- Bind deferred caption/key-load timers to their widgets to prevent callbacks after window disposal.

## 2.2.0 — development preview, included in 2.3.0

- Add short first-run teaching, source choice, one-action Apple setup and official Groq registration/key onboarding. Validate/save keys and prepare permissions in one flow, without capture.
- Collapse detailed settings behind Customize; retain defaults and offer setup again from Settings/About.
- Edit notes inline with title/format toolbar and a three-item ellipsis menu. Add Markdown input, source view, ==highlight==, Command shortcuts, lists/headings and debounced backup. Defer AI during editing and reject stale results.
- End chooses Markdown or PDF before the destination picker. Retain highlighted text in Markdown/PDF and keep original session backups. Note-only documents can also End/export without microphone capture or an API key.
- Use a main-process native microphone-permission bridge; prepare system audio separately without starting a stream. Add an embedded WKWebView for official Groq pages, with an external-browser fallback.
- Stop idle audio workers at shutdown and dispose GUI documents before Qt teardown.


## 2.1.0 — development preview, included in 2.3.0

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

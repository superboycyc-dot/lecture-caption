# User guide

Version 3.0.0 uses a DMG installer: open it, drag Lecture Caption to Applications, eject the image, then launch from Applications. Quit older versions before replacing them. The ZIP remains available for existing in-app updaters.

First-run setup requires accepting the versioned Software Use Rules. The blue rules link opens an in-app dialog; the agreement row sits immediately above the connection buttons and appears only on the first page. The single unchecked agreement explicitly includes numeric usage sharing; it must be checked to continue. Sharing can later be disabled in Settings. Closing setup cannot bypass the capture gate. Existing notes remain accessible for reading/export. Rules can be revisited from About.

If macOS blocks the first launch, follow the [illustrated four-step opening guide](INSTALL.zh-CN.md) (Chinese screenshots). It shows System Settings, Privacy & Security, Open Anyway, and the final confirmation.

The main window contains notes on the left and bilingual caption history on the right. Select microphone or system audio, then use the dedicated Start and Stop buttons. The level meter indicates incoming sound. Opacity applies to the whole window and is configured in Settings; the pin control has been removed.

When macOS asks whether Keychain can read “Lecture Caption API Key”, see the [illustrated Keychain explanation](INSTALL.zh-CN.md#看到keychain-想要使用机密信息怎么办). The helper reads only this saved API credential; enter the login-keychain password in the system dialog, not in the application key field. Allow is one-time; Always Allow permits subsequent access; Deny leaves manual API-key entry available.

Click Settings to configure your Keychain credential, backends, models, glossary, note generation, chunk length and font size. The settings dialog is hidden by default. Preferences persist across restarts.

New segments are highlighted and smoothly followed. Scroll up to read history without being pulled down; click “回到最新” to resume. The last 300 segments remain on screen; the complete transcript is stored locally. Translation updates replace their own segment, without duplicating cards.

Cloud mode needs your Groq key. Local mode uses Apple Speech and Apple Translate: select both in Settings and prepare the English/Chinese language packs. Apple translation requires macOS 15+. Speech requires supported on-device English dictation resources and Speech Recognition permission. If resources are missing, enable English Dictation in Keyboard settings. No automatic cloud fallback occurs. Disable automatic notes for key-free local captions; structured notes still require Groq and send recognized text.

Captions remain chunked near-real-time, not word-by-word interpretation. Local speech uses roughly 2–3 second chunks and is experimental. The course glossary currently applies to cloud recognition only. Local services still use system models and consume power.

Stop releases capture and discards incomplete/queued audio, marking gaps. Wait for the last sentence before stopping if you want it retained. Previously queued note generation may finish after stopping. Notes and transcript events live in ~/Library/Application Support/Lecture Caption/sessions/. No raw recording is saved. The quota display is local speech-API accounting, not provider-wide remaining quota or text-model usage.

See [Chinese guide](USER_GUIDE.zh-CN.md), [privacy](PRIVACY.md), and [README](../README.md) for API registration, installation and limitations.

When Groq returns rate-limit headers, the main window also displays the latest server request/token snapshot with its model and timestamp. This is not a billing balance or a live combined quota for all models. See [Groq rate-limit headers](https://console.groq.com/docs/rate-limits).

The compact toolbar includes input, recognition/translation backends, English/Chinese/bilingual presentation, Start/Pause, Stop and a settings icon. Audio level and usage live at the bottom. Note hints disappear on first content; refresh/folder icons remain inside the pane. Right-click notes to switch Markdown source/read view. Caption language selection changes presentation only, retaining translations in the transcript.

On macOS 26+, local recognition uses SpeechAnalyzer/SpeechTranscriber with explicit AssetInventory preparation. Use **准备 Apple 英文语音资源** in app Settings if assets are missing; toggling system Dictation is not sufficient for this engine. Older macOS uses the legacy on-device Speech API. Synthetic CS audio was verified through the native segment/recognition/Apple-translation pipeline without a cloud request; real classroom microphone accuracy still needs user verification.

Coherent captions now use borderless timestamped paragraphs: black source and blue translation on a light surface, with current-paragraph emphasis. Both Apple and Groq periodically re-recognize cumulative utterance audio and retranslate the complete current text, revising the same paragraph until a natural pause (bounded at 24 seconds for continuous speech). Previous translations remain visible while an update is pending. Notes consume completed paragraphs once; pausing preserves the last recognized draft. Repeated cumulative audio consumes more Groq speech quota than independent slices. Time ranges are approximate capture spans, not word alignment.

Live selectors remain enabled during capture. Translation-only switches keep capture and ASR running and retranslate the current paragraph; source/ASR switches save the latest recognized draft, reconnect input and discard stale-generation results. Unrecognized tail audio may be lost during input reconnection and is marked. The level indicator is green while capturing, grey when idle and a red exclamation on device errors. Daily API allowance sits beside locally counted 24h speech requests, without duration/processing-time clutter. Return-to-latest is a 32px viewport overlay: appears when browsing older text and disappears at the bottom without resizing content.

Notes append new material approximately every 30 seconds and consolidate the entire accumulated document every five minutes. Incremental requests include at most 6000 characters of new whole transcript paragraphs and 2400 characters of recent notes, with an 1800-token output budget; a single unusually long paragraph can exceed the input batch target. Consolidation sends the full note document with a size-adjusted output budget (1800–6000 tokens). The complete transcript remains on disk. Enabling notes can send earlier unprocessed text in the current lecture to the configured notes API. Provider/account limits still apply to long lectures.


## Continuation and updates

Import Markdown with the left note-toolbar folder icon and edit with the pencil. The original file is unchanged; before-edit snapshots remain in session storage. End waits for final generation and automatic revision, then opens Save As in the last successful export directory. Cancel retains the internal backup. Automatic revision (1–5 minutes, default 3) reorganizes the whole document and generates a subject title when changed; it requires automatic cloud notes and uses additional text quota. Imported notes are included in provider context.

Click the logo for version/developer information and official GitHub updates. Default automatic updates check startup/every6h and download validated newer stable Apple Silicon bundles. Only idle apps without a session auto-install; otherwise end/export and use the install button. Protected directories use the macOS administrator prompt, never app-managed passwords. The installer waits for normal exit and validates the staged replacement before swapping. Keys and session backups stay in place. No manual revise action is exposed; source runs do not replace app bundles.


## First run and inline notes

The first-run guide explains Groq-backed captions, translation and notes. Connect prepares Apple backup resources and selected-input permissions, then opens the official embedded Groq registration/key page (external browser fallback). Authenticate, create and copy a key, then click Next to validate and save to Keychain. With an empty field, this explicit Next action reads the clipboard once; it is never watched. Apple backup preparation failure does not prevent connecting Groq. Only explicit Skip selects local captions and disables notes. Setup never starts capture.

The final guide is a grey overlay on the actual workspace, with white arrows, step counters, Next and Skip. Highlighted controls cannot start capture during the tutorial. Detailed settings use a collapsed “高级设置” disclosure. Automatic updates default on, with opt-out. Revisit setup/tutorial from Settings or About.

Notes now edit in place. The toolbar contains title, bold/italic/headings/lists/highlight/strike; the ellipsis contains only source view, immediate summary (立即整理) and folder. ==highlight== and standard inline Markdown input are supported, with Command+B/I/H and Command+Shift+X. Source mode edits the same document. AI waits during active editing and stale responses are rejected. End offers Markdown/PDF then a destination; note-only documents can export without capture/key. Rich edits normalize Markdown; code stays literal and LaTeX remains source text.


## Optional usage sharing (2.4)

The first-run agreement explicitly includes numeric usage sharing, with a visible disclosure. It starts unchecked and must be checked to continue; no second choice is needed. Sharing can later be withdrawn in Settings. Only future recording counts, active capture duration and source/translation word/character lengths are recorded; no content, credentials or stable device identifier is sent. Pause/resume stays one lecture and revised paragraphs replace prior length counts. SQLite retains unacknowledged snapshots for later retry, including after relaunch. No background OS launch service is installed. Opt-out clears local queue rows; in-flight requests may already have reached the receiver. Funnel/upstream diagnostics may see IP addresses.

The v2.4.0 public HTTPS receiver passed [independent tailnet-external acceptance](https://github.com/superboycyc-dot/lecture-caption/actions/runs/40411300895). Ordinary users need no Tailscale or custom server address. Sharing remains off by default and only starts after explicit consent; status is visible in Settings.


## 2.4.2 workflow updates

Finish retains the internal Markdown backup and automatically writes a timestamped PDF to Desktop by default. Change the automatic PDF folder in Settings. The completion dialog offers Save As MD, Save As PDF, or Done; a write failure is reported without claiming success. Save As remembers its own directory.

Common TeX math using `\[...\]`, `\(...\)`, `$$...$$`, or `$...$` is rendered offline and embedded in PDFs. Double-click a formula or edit source Markdown; original math syntax survives Markdown export. Unsupported macros remain literal source (the renderer supports a TeX subset).

Groq setup shows a fixed key name (`Lecture Caption`), No expiration, and a reminder to copy the generated key. Apple speech and translation resources are prepared independently; retry/download controls are available after Groq setup and in Settings. On macOS 15–25, use Keyboard → Dictation for English (US) assets; macOS 26+ supports in-app speech asset installation.

Groq recognition/translation does not enable automatic notes. Enable automatic Markdown notes in Settings; use the notes menu's immediate summary to process recognized text still held in the current session. Disabled state and provider failures are now visible. Merely focusing the editor no longer blocks summaries; real edits defer them until saved and idle.

Provider failures show safe reasons and remain visible until a successful notes request. Network/timeouts, 429 and temporary server errors retry at most twice with backoff. Authentication/permission errors do not retry. Pause/End cancels audio retries. End exports transcript Markdown beside the PDF; “另存转录” saves the recognized original at any time.


### Recent notes

Choose **打开最近笔记** in the empty notes pane, or use **⋯ → 最近笔记**. The in-app chooser lists up to 50 local backups by modification time, with a title, date/time and the first 15 body characters. Click outside or press Esc to dismiss. Finish capture and processing before switching notes. Viewing is local; editing or continuing creates a separate session and preserves the original.

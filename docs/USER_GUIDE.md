# User guide

The main window contains notes on the left and bilingual caption history on the right. Select microphone or system audio, then use the dedicated Start and Stop buttons. The level meter indicates incoming sound. Opacity applies to the whole window and is configured in Settings; the pin control has been removed.

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

Notes now revise one coherent document, backed by a cumulative transcript.md. Long lectures send the full previous note document, about 18000 characters of recent whole transcript paragraphs, and all unprocessed text; the complete original stays on disk. Enabling notes sends this accumulated context, including earlier locally recorded content in the current lecture, to the configured notes API.

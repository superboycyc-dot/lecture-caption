# User guide

The main window contains notes on the left and bilingual caption history on the right. Select microphone or system audio, then use the dedicated Start and Stop buttons. The level meter indicates incoming sound. Pin and opacity apply to the whole window.

Click Settings to configure your Keychain credential, backends, models, glossary, note generation, chunk length and font size. The settings dialog is hidden by default. Preferences persist across restarts.

New segments are highlighted and smoothly followed. Scroll up to read history without being pulled down; click “回到最新” to resume. The last 300 segments remain on screen; the complete transcript is stored locally. Translation updates replace their own segment, without duplicating cards.

Cloud mode needs your Groq key. Local mode uses Apple Speech and Apple Translate: select both in Settings and prepare the English/Chinese language packs. Apple translation requires macOS 15+. Speech requires supported on-device English dictation resources and Speech Recognition permission. If resources are missing, enable English Dictation in Keyboard settings. No automatic cloud fallback occurs. Disable automatic notes for key-free local captions; structured notes still require Groq and send recognized text.

Captions remain chunked near-real-time, not word-by-word interpretation. Local speech uses roughly 2–3 second chunks and is experimental. The course glossary currently applies to cloud recognition only. Local services still use system models and consume power.

Stop releases capture and discards incomplete/queued audio, marking gaps. Wait for the last sentence before stopping if you want it retained. Previously queued note generation may finish after stopping. Notes and transcript events live in ~/Library/Application Support/Lecture Caption/sessions/. No raw recording is saved. The quota display is local speech-API accounting, not provider-wide remaining quota or text-model usage.

See [Chinese guide](USER_GUIDE.zh-CN.md), [privacy](PRIVACY.md), and [README](../README.md) for API registration, installation and limitations.

When Groq returns rate-limit headers, the main window also displays the latest server request/token snapshot with its model and timestamp. This is not a billing balance or a live combined quota for all models. See [Groq rate-limit headers](https://console.groq.com/docs/rate-limits).

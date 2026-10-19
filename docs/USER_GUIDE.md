# User guide

See the [Chinese step-by-step guide](USER_GUIDE.zh-CN.md) for the current UI labels.

## Inputs

Choose one input at a time: the Mac microphone (in-person class) or system audio (calls, video and browser playback). System audio uses ScreenCaptureKit; it does not save screen images and requires the corresponding macOS capture permission. Other sounds playing on the Mac can also be captured. It does not mix in your own microphone.

## Credentials

Create a Groq key in its official console. Paste into the masked field and test. Keep “验证成功后保存到钥匙串” enabled to save after success, or press “保存 key”. Deleting a saved key clears the app field and disables automatic re-save; it does not revoke the provider key. Cancelled/locked Keychain access falls back to manual entry, not plaintext storage. A SHA-256 digest identifies the pair of configured endpoint URLs; the secret itself is stored reversibly by the OS Keychain, because hashing alone cannot authenticate API calls.

## Windows and notes

Pin and opacity work independently per window. Opacity applies to text and background together. Settings currently reset on restart. Open the notes window to read or copy raw Markdown, request immediate organization, or open its folder. The text may need manual verification. Notes accumulate per app run; pause/resume continues the same document.

## Custom servers

Copy `config.example.json` into the app data directory as `config.json` and edit the base URLs/model IDs. Speech expects `/audio/transcriptions` with multipart WAV. Text expects `/chat/completions`, messages and `max_completion_tokens`. A single credential is currently shared between both configured providers. Do not configure an unrelated server if it should not receive that credential. Exact endpoint pairs have separate Keychain entries. Changes require restarting.

The built-in connection check tests the speech server's `/models` endpoint. When text and speech endpoints differ, successful validation does not prove the text server is reachable. First validate using a small test lecture.

## Troubleshooting

- No sound: inspect the input selection, macOS permission and volume meter; lower the noise threshold for quiet speech.
- System audio denied: enable the app in Privacy & Security → Screen & System Audio Recording and relaunch.
- 401/403: check the credential and model permissions.
- 429: stop, inspect provider limits, then resume when available. Notes retain pending source text; the app does not bypass quotas.
- Model missing: enter a current available model ID; provider model lists can change.
- Pause: wait for the last sentence's caption first if it must be retained.

## Modified Qt libraries

The app is an onedir PyInstaller bundle, with dynamically loaded Qt/PySide libraries. Source, version pins, build scripts and component notices accompany releases. You may rebuild against compatible modified libraries and ad-hoc sign the resulting app; no verification mechanism is added to block such replacements. See `licenses/` and `THIRD_PARTY_NOTICES.md`.

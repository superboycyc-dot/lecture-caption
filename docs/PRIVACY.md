# Privacy and data flow

This app has no project-operated server or analytics. It does **not** mean all computation is local.

| Data | Destination | When |
|---|---|---|
| Microphone or system audio chunks | Configured speech API (Groq by default) | After Start, while capture is active |
| Recognized speech | Configured translation and notes API | During translation and notes processing |
| API credential | Configured API hosts, as Authorization | Connection tests and API calls |
| API credential | macOS login Keychain, service `local.lecturecaption.api` | Explicit save / enabled save after successful test |
| Notes and transcript events | Local app-data directory | During capture/notes processing |
| Diagnostic messages / local quota estimate | Local logs directory | At runtime |

No raw audio file, screen frame, credential, or personal document is included in release assets. System audio mode uses ScreenCaptureKit audio callbacks; it can include sounds from other apps. Only one input is used at a time.

Saving is optional. Keys are passed to the native Keychain helper over stdin, not arguments. The in-process app and helper temporarily possess the original key to authenticate. Keychain item identifiers hash the endpoint pair, not the key. This is not end-to-end encrypted inference; your selected providers' retention and data-use terms apply.

Local data remains until you remove it. Back up your notes before deleting the app-data directory. Use the app's delete control to remove its current endpoint pair's Keychain item; removing the app alone does not revoke provider credentials. No automatic cloud backup is implemented.

Maintainers do not need your key or recording to diagnose basic bugs. Redact logs and examples before posting an issue. CI tests use mock responses and synthetic audio, not real provider credentials.

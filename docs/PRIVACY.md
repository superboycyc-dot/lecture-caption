# Privacy and data flow

This app has no project-operated server or analytics. It does **not** mean all computation is local.

| Data | Destination | When |
|---|---|---|
| Microphone or system audio chunks | Configured speech API (Groq by default) | After Start, only in cloud speech mode |
| Microphone or system audio chunks | Apple on-device Speech framework | After Start, only in Apple speech mode; requiresOnDeviceRecognition is enforced |
| Recognized speech | Configured translation API | Only in cloud translation mode |
| Recognized speech | Apple Translation.framework on-device | Only in Apple translation mode, with installed languages |
| Recognized speech | Configured notes API | When automatic notes are enabled; pending notes may finish after Stop |
| API credential | Configured API hosts, as Authorization | Connection tests and API calls |
| API credential | macOS login Keychain, service `local.lecturecaption.api` | Explicit save / enabled save after successful test |
| Notes and transcript events | Local app-data directory | During capture/notes processing |
| Diagnostic messages / local quota estimate | Local logs directory | At runtime |

No raw audio file, screen frame, credential, or personal document is included in release assets. System audio mode uses ScreenCaptureKit audio callbacks; it can include sounds from other apps. Only one input is used at a time.

Saving is optional. Keys are passed to the native Keychain helper over stdin, not arguments. The in-process app and helper temporarily possess the original key to authenticate. Keychain item identifiers hash the endpoint pair, not the key. This is not end-to-end encrypted inference; your selected providers' retention and data-use terms apply.

Local data remains until you remove it. Back up your notes before deleting the app-data directory. Use the app's delete control to remove its current endpoint pair's Keychain item; removing the app alone does not revoke provider credentials. No automatic cloud backup is implemented.

Maintainers do not need your key or recording to diagnose basic bugs. Redact logs and examples before posting an issue. CI tests use mock responses and synthetic audio, not real provider credentials.

Apple backends do not silently fall back to cloud. Translation language assets are downloaded only through the explicit preparation flow in Settings. Apple may collect system API usage/performance metrics according to its own policies; application-owned analytics are not added. Turning off automatic notes prevents newly recognized text being queued for notes; previously queued notes may still complete. No key is required when both backends are Apple and notes are disabled. Preferences are stored using a fixed whitelist that excludes credentials.

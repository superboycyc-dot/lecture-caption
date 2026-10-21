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

Continuous-document mode saves a canonical transcript.md alongside revision events. When note generation is enabled, requests include previous notes, recent continuous transcript paragraphs (approximately 18000 characters), and all unprocessed text. Earlier locally recorded text in the current lecture may therefore become part of note context when notes are enabled later. Translation-only switching retains capture; other input changes start a new generation, reject stale callbacks/results and preserve already recognized drafts. No private runtime data is used in tests.

Imported Markdown is copied into the local note document; the original selected file is not modified. Editing keeps before-edit snapshots. When cloud notes are enabled, imported/edited notes are sent as part of the existing-document context, including automatic second-pass revision. End exports to a user-chosen path while retaining internal backups. The last export directory is stored locally.

Automatic updates default on and contact only the public official GitHub repository for release metadata and assets at startup/every6h. No API key, transcript, note or recording accompanies update requests. Newer stable assets are checked against release SHA-256 sums, bundle identifier/version and ad-hoc code-signature validity. Installation waits for normal exit; macOS handles any administrator password prompt. Disable automatic update in Settings/About to stop background requests. No telemetry is added.

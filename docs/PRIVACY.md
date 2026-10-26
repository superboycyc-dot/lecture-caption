# Privacy and data flow

Public v2.3.0 has no project-operated usage analytics. The local v2.4.0 preview introduces optional developer-operated numeric usage statistics, disabled unless the user opts in. It does **not** mean all computation is local.

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
| Recording count, capture duration and source/translation word/character counts, a random per-lecture event ID, revision and UTC date | Local SQLite outbox; developer-operated receiver once publicly verified | Only after explicit opt-in; public upload is currently gated off |

No raw audio file, screen frame, credential, or personal document is included in release assets. System audio mode uses ScreenCaptureKit audio callbacks; it can include sounds from other apps. Only one input is used at a time.

Saving is optional. Keys are passed to the native Keychain helper over stdin, not arguments. The in-process app and helper temporarily possess the original key to authenticate. Keychain item identifiers hash the endpoint pair, not the key. This is not end-to-end encrypted inference; your selected providers' retention and data-use terms apply.

Local data remains until you remove it. Back up your notes before deleting the app-data directory. Use the app's delete control to remove its current endpoint pair's Keychain item; removing the app alone does not revoke provider credentials. No automatic cloud backup is implemented.

Maintainers do not need your key or recording to diagnose basic bugs. Redact logs and examples before posting an issue. CI tests use mock responses and synthetic audio, not real provider credentials.

Apple backends do not silently fall back to cloud. Translation language assets are downloaded through explicit setup/preparation actions in the first-run guide or Settings. Apple may collect system API usage/performance metrics according to its own policies; optional usage reporting follows the explicit-consent rules below. Turning off automatic notes prevents newly recognized text being queued for notes; previously queued notes may still complete. No key is required when both backends are Apple and notes are disabled. Preferences are stored using a fixed whitelist that excludes credentials.

Continuous-document mode saves a canonical transcript.md alongside revision events. When note generation is enabled, requests include previous notes, recent continuous transcript paragraphs (approximately 18000 characters), and all unprocessed text. Earlier locally recorded text in the current lecture may therefore become part of note context when notes are enabled later. Translation-only switching retains capture; other input changes start a new generation, reject stale callbacks/results and preserve already recognized drafts. No private runtime data is used in tests.

Imported Markdown is copied into the local note document; the original selected file is not modified. Editing keeps before-edit snapshots. When cloud notes are enabled, imported/edited notes are sent as part of the existing-document context, including automatic second-pass revision. End exports to a user-chosen path while retaining internal backups. The last export directory is stored locally.

Automatic updates default on and contact only the public official GitHub repository for release metadata and assets at startup/every6h. No API key, transcript, note or recording accompanies update requests. Newer stable assets are checked against release SHA-256 sums, bundle identifier/version and ad-hoc code-signature validity. Installation waits for normal exit; macOS handles any administrator password prompt. Disable automatic update in Settings/About to stop background requests. Update requests contain no usage statistics; optional usage reporting is a separate opt-in feature.

First-run Connect/Skip actions prepare Apple speech/translation backup resources and the selected input permissions; preparation never opens an audio stream. Groq is the primary setup route; only explicit Skip selects local captions and disables notes. Microphone consent is requested in the main app process. Apple may require a System Settings change/restart after denial. The optional Groq setup browser uses WebKit to display the official HTTPS account/key page; account authentication and WebKit cookies are handled by the web view/provider, without script injection, DOM/password inspection or application logging. Clipboard text is read only on the explicitly labeled Next action with an empty key field, never watched. The app stores only the copied API key through its normal Keychain mechanism. Model-list validation does not send audio/notes.

Inline edits remain in local backups; enabling notes or pressing immediate summary (立即整理) can send the existing document and recognized source to the configured notes provider. AI is deferred during active editing. Markdown/PDF export writes only to the user-selected path and retains the internal backup. No key means no cloud client is created.


## Optional numeric usage (v2.4.0 local preview)

First-run setup and Settings contain an unchecked optional choice. Selecting it does not grant microphone access or start capture; declining does not block one-action permission preparation or any app feature. Only future successful capture and future recognized paragraphs are counted. Imported/edited notes and prior transcripts are never scanned for statistics. Enabling mid-lecture excludes the already-started paragraph to avoid retroactive collection.

One logical lecture counts once across pause/resume and input/model switching. Monotonic capture time excludes permission waits and pauses. Live recognition/translation revisions replace paragraph length counts instead of accumulating intermediate strings. Only numeric lengths are stored, never text or audio. Latin-letter/number tokens and Unicode letter/number characters are separate measures, not added together. No stable device ID, account, filename or exact start timestamp is sent.

The SQLite outbox uses WAL/FULL transactions and cumulative event revisions. A separate worker checkpoints active duration about once per second, independent of networking; abrupt termination can lose the most recent uncheckpointed duration. Failed/absent/malformed acknowledgements retain the records across restarts. Upload uses HTTPS, no redirects or speech credentials, bounded responses/timeouts and exponential backoff with jitter/Retry-After. There is no OS launch agent: retry runs while the app is open or at the next app launch, not while closed. Already-acknowledged revisions remain local to support subsequent cumulative revisions within the lecture.

Turning sharing off stops subsequent collection/upload and removes local queue rows; requests already in flight may have reached the receiver. Enabling again does not backfill earlier text. This is not a server-side deletion feature. Local outbox failures are displayed without stopping capture.

The deployed receiver is not yet publicly DNS-resolvable. PUBLIC_UPLOAD_READY remains false and DEFAULT_USAGE_ENDPOINT is empty in this preview, even if a machine can reach a private Tailscale route. Do not enable the release gate until tailnet-external ingestion and restricted-route checks pass. Consent-enabled statistics currently remain local awaiting integration. No real customer data has been sent in tests.

The receiver runs on the developer's home server. Tailscale Funnel and upstream/system diagnostics may process or retain source IP information outside the receiver's control; do not describe the full network path as anonymous or promise zero IP logs. Public numeric ingestion is unauthenticated and may be forged; totals are product-use estimates, not billing records or reliable unique-user counts. Management exposure beyond Funnel remains a separate deployment audit item.

# Privacy and data flow

Public v2.3.0 has no project-operated usage analytics. v2.4.0 introduced developer-operated numeric usage statistics. In v2.4.1 the required first-run agreement explicitly includes usage sharing, starts unchecked, and must be checked to continue. Sharing can later be withdrawn in Settings. It does **not** mean all computation is local.

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
| Recording count, capture duration and source/translation word/character counts, a random per-lecture event ID, revision and UTC date | Local SQLite outbox; verified developer-operated HTTPS receiver; connection IP recorded only after current consent | Only after the explicit combined first-run agreement; no sharing before acceptance |

No raw audio file, screen frame, credential, or personal document is included in release assets. System audio mode uses ScreenCaptureKit audio callbacks; it can include sounds from other apps. Only one input is used at a time.

Saving is optional. Keys are passed to the native Keychain helper over stdin, not arguments. The in-process app and helper temporarily possess the original key to authenticate. Keychain item identifiers hash the endpoint pair, not the key. This is not end-to-end encrypted inference; your selected providers' retention and data-use terms apply.

Local data remains until you remove it. Back up your notes before deleting the app-data directory. Use the app's delete control to remove its current endpoint pair's Keychain item; removing the app alone does not revoke provider credentials. No automatic cloud backup is implemented.

Maintainers do not need your key or recording to diagnose basic bugs. Redact logs and examples before posting an issue. CI tests use mock responses and synthetic audio, not real provider credentials.

Apple backends do not silently fall back to cloud. Translation language assets are downloaded through explicit setup/preparation actions in the first-run guide or Settings. Apple may collect system API usage/performance metrics according to its own policies; optional usage reporting follows the explicit-consent rules below. Turning off automatic notes prevents newly recognized text being queued for notes; previously queued notes may still complete. No key is required when both backends are Apple and notes are disabled. Preferences are stored using a fixed whitelist that excludes credentials.

Notes append new material approximately every 30 seconds and consolidate the entire accumulated document every five minutes. Incremental requests include at most 6000 characters of new whole transcript paragraphs and 2400 characters of recent notes, with an 1800-token output budget; a single unusually long paragraph can exceed the input batch target. Consolidation sends the full note document with a size-adjusted output budget (1800–6000 tokens). The complete transcript remains on disk. Enabling notes can send earlier unprocessed text in the current lecture to the configured notes API. Provider/account limits still apply to long lectures. Translation-only switching retains capture; other input changes reject stale results and preserve recognized drafts. Tests use synthetic data only.

Imported Markdown is copied into the local note document; the original selected file is not modified. Editing keeps before-edit snapshots. When cloud notes are enabled, imported/edited notes are sent as part of the existing-document context, including automatic second-pass revision. End exports to a user-chosen path while retaining internal backups. The last export directory is stored locally.

Automatic updates default on and contact only the public official GitHub repository for release metadata and assets at startup/every6h. No API key, transcript, note or recording accompanies update requests. Newer stable assets are checked against release SHA-256 sums, bundle identifier/version and ad-hoc code-signature validity. Installation waits for normal exit; macOS handles any administrator password prompt. Disable automatic update in Settings/About to stop background requests. Update requests contain no usage statistics; usage sharing requires the disclosed first-run agreement.

First-run Connect/Skip actions prepare Apple speech/translation backup resources and the selected input permissions; preparation never opens an audio stream. Groq is the primary setup route; only explicit Skip selects local captions and disables notes. Microphone consent is requested in the main app process. Apple may require a System Settings change/restart after denial. The optional Groq setup browser uses WebKit to display the official HTTPS account/key page; account authentication and WebKit cookies are handled by the web view/provider, without script injection, DOM/password inspection or application logging. Clipboard text is read only on the explicitly labeled Next action with an empty key field, never watched. The app stores only the copied API key through its normal Keychain mechanism. Model-list validation does not send audio/notes.

Inline edits remain in local backups; enabling notes or pressing immediate summary (立即整理) can send the existing document and recognized source to the configured notes provider. AI is deferred during active editing. Markdown/PDF export writes only to the user-selected path and retains the internal backup. No key means no cloud client is created.


## Optional numeric usage (v2.4.0)

The current first-run page has one unchecked agreement labeled “同意《软件使用规则》并分享用量统计”, with a visible usage-and-IP disclosure. It must be checked to continue setup/capture and simultaneously enables usage sharing; the rules dialog has no additional checkbox. Settings retains withdrawal. Opening the rules does not grant consent. Rules version acceptance and sharing state are stored separately so later withdrawal persists. The row appears only on the first setup page. A previously opted-in numeric queue is held until current rules are accepted. Acceptance never grants microphone permission or starts capture. Only future successful capture and future recognized paragraphs are counted. Imported/edited notes and prior transcripts are never scanned for statistics. Enabling mid-lecture excludes the already-started paragraph to avoid retroactive collection.

One logical lecture counts once across pause/resume and input/model switching. Monotonic capture time excludes permission waits and pauses. Live recognition/translation revisions replace paragraph length counts instead of accumulating intermediate strings. Only numeric lengths of content are stored, never text or audio; consented upload connection IPs are stored separately as described below. Latin-letter/number tokens and Unicode letter/number characters are separate measures, not added together. No stable device ID, account, filename or exact start timestamp is sent.

The SQLite outbox uses WAL/FULL transactions and cumulative event revisions. A separate worker checkpoints active duration about once per second, independent of networking; abrupt termination can lose the most recent uncheckpointed duration. Failed/absent/malformed acknowledgements retain the records across restarts. Upload uses HTTPS, no redirects or speech credentials, bounded responses/timeouts and exponential backoff with jitter/Retry-After. There is no OS launch agent: retry runs while the app is open or at the next app launch, not while closed. Already-acknowledged revisions remain local to support subsequent cumulative revisions within the lecture.

Turning sharing off stops subsequent collection/upload and removes local queue rows; requests already in flight may have reached the receiver. Enabling again does not backfill earlier text. This is not a server-side deletion feature. Local outbox failures are displayed without stopping capture.

The public receiver at https://orangepiaipro-us.taile2de37.ts.net/v1/usage/batch passed independent GitHub-hosted public DNS, verified TLS, ingestion, revision/retry, rate-limit and restricted-route acceptance on 2026-10-26. PUBLIC_UPLOAD_READY is enabled for this release; sharing itself remains off until explicit consent. Ordinary users do not need Tailscale or a custom server address. Tests used random event IDs and fictional numbers on the dedicated test date 2000-01-01, never customer recordings or text. See [acceptance evidence](deployment/usage-public-acceptance.json).

The receiver runs on the developer's home server. Tailscale Funnel and upstream/system diagnostics may process or retain source IP information outside the receiver's control; do not describe the full network path as anonymous or promise zero IP logs. Public numeric ingestion is unauthenticated and may be forged; totals are product-use estimates, not billing records or reliable unique-user counts. Management exposure beyond Funnel remains a separate deployment audit item.

Transient provider errors retry the same request at most twice with exponential backoff. HTTP 429 honors numeric Retry-After and keeps per-model cooldowns; long cooldowns defer to later attempts. Pause/End cancels audio retries and shutdown cancels all retries. No implicit provider or paid-service fallback is added. Request/response bodies and credentials are never shown in diagnostics. Recognized transcript Markdown is also exported beside the automatic PDF on End; “另存转录” exports a separate copy.


## Consented upload IP recording (unreleased)

Rules 2026-10-27.1 disclose upload connection IP collection. Previous acceptance is insufficient: upload stays paused until the updated rules are explicitly accepted. Each opted-in usage request includes `X-Lecture-Usage-IP: 1`; the receiver records the observed source IP, receipt time and batch event IDs for that upload in a separate restricted table, without changing cumulative event deduplication. Old clients without the header do not enable IP recording. No third-party IP lookup is performed. Trusted loopback Tailscale forwarding is used only under the existing explicit proxy configuration; arbitrary forwarded addresses are ignored. VPN/proxy exit addresses can differ from the user’s own address. IP records are for source analysis and abuse diagnosis, not public display or advertising. They expire after 30 days while the receiver is running; the receiver checks expiry every five seconds and on uploads. Retained backups exclude IP records. Opt-out stops future collection, but is not retrospective server deletion.

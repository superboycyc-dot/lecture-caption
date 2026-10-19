# Security policy

Only the latest released minor series (currently 0.3.x) is actively maintained. This is an early personal project, without a guaranteed response SLA.

Never post an API key or private audio in a public issue. Use this repository's **Security → Report a vulnerability** feature for credential disclosure or other sensitive reports. If that feature is unavailable, open a minimal issue requesting a private reporting channel, without exploit details or personal data. A maintainer will arrange an appropriate channel.

If a key is exposed, revoke/rotate it at its provider; deleting a GitHub comment or local key does not revoke it. The app's Keychain helper is not an authorization boundary against an already-compromised user account. Users control configured endpoint hosts and should not send their credential to untrusted hosts.

Release packages are ad-hoc signed and checksumed, not Apple Developer ID notarized. Checksums detect transfer changes; they do not establish maintainer identity independently of the release channel.

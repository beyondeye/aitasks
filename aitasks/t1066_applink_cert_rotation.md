---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [applink, applink_security]
anchor: 985
created_at: 2026-06-24 22:27
updated_at: 2026-06-25 09:55
---

## Origin

Risk-mitigation ("after") follow-up for t985, created at Step 8d after implementation landed. Scoped out of t985 as a heavyweight lifecycle item (user-approved deferral).

## Risk addressed

10-year static self-signed cert residual · the applink TLS cert (`tls.py`, `_CERT_VALIDITY_DAYS = 3650`) is long-lived with no rotation; a compromised key is usable for a decade.

## Goal

Add cert rotation for the applink self-signed cert: generate on a shorter validity (e.g. 90-180 days), detect near-expiry and re-mint, and provide a client re-pair flow for the changed fingerprint (the QR fingerprint is pinned for the pairing lifetime, so a new cert breaks existing pairings — the phone must re-pair). Coordinate any wire/pairing implications with `aidocs/applink/protocol.md` and document the rotation policy in `aidocs/applink/security.md` (currently listed there as a deferred residual). When needed: before the 10-year cert is anywhere near a real expiry concern, or sooner if key-rotation hygiene is desired.

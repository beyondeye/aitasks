---
priority: medium
effort: low
depends: [t822_4]
issue_type: feature
status: Implementing
labels: [applink]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-25 14:08
updated_at: 2026-06-15 18:56
---

Add a `name=<urlencoded(socket.gethostname())>` query parameter to the QR URL emitted by the applink TUI. Per the updated spec in `aidocs/applink/protocol.md` §Pairing flow line 97.

`name=` is OPTIONAL and additive: older mobile clients that don't yet parse it are unaffected (§Versioning additive-fields rule). Strictly a single-line change to the QR-URL builder plus a unit test.

## Implementation hints

- Locate the QR-URL builder in the applink TUI (the code that emits `applink://<lan-ip>:<port>/pair?t=...&fp=...`).
- Append `&name=<urlencoded(socket.gethostname())>`. Use `urllib.parse.quote(..., safe='')` so spaces / non-ASCII hostnames are safely encoded.
- Add a unit test that confirms `name=` is present and matches `urlencoded(socket.gethostname())`.

## Cross-references

- Sister task in mobile repo: `aitasks_mobile/aitasks/archived/t13/t13_2_sister_qr_add_hostname_field.md` (after archival).
- Mobile-side parser change: `aitasks_mobile/aitasks/t13/t13_4_qr_url_parser.md` — the parser treats `name=` as optional.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T15:56:06Z status=pass attempt=1 type=human

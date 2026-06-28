---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [applink, applink_security]
anchor: 985
created_at: 2026-06-24 22:27
updated_at: 2026-06-25 09:55
boardidx: 180
---

## Origin

Risk-mitigation ("after") follow-up for t985, created at Step 8d after implementation landed. Scoped out of t985 as a heavyweight lifecycle item (user-approved deferral; bearer TTL kept at 7 days in t985).

## Risk addressed

7-day static bearer residual · bearers (`sessions.py`, `DEFAULT_BEARER_TTL = 7*24*3600`) are static for their whole TTL; a leaked bearer is usable for up to 7 days.

## Goal

Rotate the bearer on each `resume` so a leaked bearer's useful life is shortened: issue a fresh bearer in exchange for the presented one, invalidating the old, and return it to the client. This is a wire-protocol + mobile-client change (the phone must accept and persist the rotated bearer on resume) — coordinate with `aidocs/applink/protocol.md` and the mobile app (`../aitasks_mobile`). Update `aidocs/applink/security.md` (listed there as a deferred residual). When needed: if bearer-theft exposure on a shared/less-trusted host becomes a concern, or alongside any broader session-security hardening.

---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 12:29
updated_at: 2026-06-24 19:28
boardidx: 160
---

## Origin

Risk-mitigation ("after") follow-up for t822_7 (applink WebSocket listener), created at Step 8d after implementation landed.

## Risk addressed

A new **TLS network listener is fresh attack surface** (token/bearer handling, cert lifecycle, DoS, input validation) shipped without a dedicated security review. · severity: high · → mitigation: applink_security_review_hardening

## Goal

Perform a security review and hardening pass on the `ait applink` WebSocket control-plane listener landed in t822_7, then implement the agreed fixes. Areas to cover:

- **TLS:** cipher-suite / protocol-version selection (currently default `PROTOCOL_TLS_SERVER`), self-signed cert rotation & lifecycle (currently a single long-lived 10-year cert under `aitasks/metadata/applink_sessions/`), private-key permissions.
- **Pairing tokens:** entropy (256-bit urlsafe), single-use enforcement, TTL, replay resistance.
- **Bearers:** entropy, expiry/TTL policy, revocation completeness, persistence-at-rest of `sessions.json` (currently plaintext, gitignored).
- **DoS / abuse:** connection limits, per-IP rate-limiting, unauthenticated-frame flood handling, max frame/payload size, slow-loris on the TLS handshake.
- **Input validation:** strict envelope/payload schema validation, pane_id/window_id/keys sanitization before reaching tmux send-keys.
- **Audit logging:** log denied verbs (PERMISSION_DENIED) and auth failures for observability (deferred in protocol/permissions docs).

Deliverables: a short threat-model note, the implemented hardening changes, and tests where practical. Coordinate any wire-protocol implications with `aidocs/applink/protocol.md` and the mobile app (`aitasks_mobile`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-24T16:28:41Z status=pass attempt=1 type=human

---
priority: medium
effort: high
depends: []
issue_type: documentation
status: Ready
labels: [applink, applink_connectivity]
gates: [risk_evaluated]
anchor: 1061
created_at: 2026-07-02 23:46
updated_at: 2026-07-02 23:46
---

**A4 of the t1061 paired decomposition** (see
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md`). Phase-3
relay-broker **design task — design-only, no implementation**. This is the
design task `aidocs/applink/protocol.md` §Roadmap explicitly defers "to be
created after the Phase 1 implementation has landed" — it has. Independent of
the other children (can run any time).

## Deliverable

`aidocs/applink/relay_broker_design.md` — a complete design ready for its own
implementation decomposition later.

## Design scope

- **Outbound-dial model:** PC dials **out** to a (self-hostable) broker; phone
  connects to the broker; broker stitches sessions. Validated by Claude Code
  Remote Control's outbound-HTTPS-only architecture (never opens inbound
  ports; CGNAT/firewall immune). See
  https://code.claude.com/docs/en/remote-control
- **New QR scheme** `applink://<broker-host>/r/<session-id>` — the scheme
  change protocol.md reserves for Phase 3 (Phase 2 must not change the
  scheme).
- **Trust:** broker pinning replaces direct cert pinning, plus **end-to-end
  key exchange** so the broker never sees frame contents — its own crypto
  spec + a security-review addendum extending `aidocs/applink/security.md`.
- **Design considerations to capture explicitly:**
  - `MAX_PER_IP=8` (server.py) collapses behind a relay — all clients share
    the broker's source IP; admission control must move to a different key.
  - Short-lived, purpose-scoped credentials expiring independently (Remote
    Control pattern; feeds t1067 bearer rotation).
  - Reconnect semantics: map the existing `Suspended → Connected` state
    machine onto relay session stitching.
  - Persistent PTY/session daemon surviving restarts (9remote,
    https://github.com/decolua/9remote) as a resume-robustness option.
  - Phase-4 WebRTC signaling as a forward-compatibility section **only**
    (relay used for signaling; frames P2P; `ice=` param per protocol.md).

## Verification

- Design review against protocol.md invariants (envelope, pairing flow,
  verbs/permissions unchanged; only connectivity changes).
- Explicit checklist showing each "design considerations" bullet above is
  addressed in the document.

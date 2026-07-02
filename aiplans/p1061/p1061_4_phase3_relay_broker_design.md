---
Task: t1061_4_phase3_relay_broker_design.md
Parent Task: aitasks/t1061_applink_outside_network_connectivity_roadmap.md
Sibling Tasks: aitasks/t1061/t1061_1_*.md, aitasks/t1061/t1061_2_*.md, aitasks/t1061/t1061_3_*.md, aitasks/t1061/t1061_5_*.md
Archived Sibling Plans: aiplans/archived/p1061/p1061_*_*.md
Worktree: aiwork/t1061_4_phase3_relay_broker_design
Branch: aitask/t1061_4_phase3_relay_broker_design
Base branch: main
---

# Plan: A4 — Phase-3 relay-broker design (design-only)

Independent child; **no implementation** — produces
`aidocs/applink/relay_broker_design.md`. The task body carries the full
brief; parent plan `aiplans/p1061_applink_outside_network_connectivity_roadmap.md`
has the roadmap context.

## Steps

1. Re-read `aidocs/applink/protocol.md` (§Roadmap Phase 3/4, invariants that
   carry forward: envelope, pairing flow, state machine, verbs/permissions)
   and `aidocs/applink/security.md`.
2. Design document sections:
   - Outbound-dial architecture (PC → broker; phone → broker; session
     stitching); self-hosting story.
   - QR scheme `applink://<broker-host>/r/<session-id>` (the reserved Phase-3
     scheme change) + pairing-flow mapping.
   - Trust: broker pinning + end-to-end key exchange (broker never sees frame
     contents) — crypto spec + security-review addendum extending
     `security.md`.
   - Admission control behind a relay (`MAX_PER_IP=8` collapses — key on
     session/bearer instead).
   - Short-lived purpose-scoped credentials (Remote Control pattern; feeds
     t1067).
   - Reconnect: `Suspended → Connected` over relay session stitching;
     persistent-session-daemon option (9remote).
   - Phase-4 WebRTC forward-compatibility section only (`ice=` param).
3. Checklist confirming each design-consideration bullet from the task body is
   addressed.

## Verification

- Design review against protocol.md invariants; checklist complete; no
  implementation files touched.

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9.

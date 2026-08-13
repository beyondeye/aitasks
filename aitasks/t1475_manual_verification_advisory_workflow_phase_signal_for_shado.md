---
priority: medium
effort: medium
depends: [1420]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1420]
followup_kind: manual_verification
created_at: 2026-08-10 16:21
updated_at: 2026-08-13 23:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1420

## Verification Checklist

- [ ] ait minimonitor: the docked followed-agent panel shows a `phase:` line, and it REPAINTS (not frozen at build) when the followed agent moves from the Step-6 plan checkpoint to the Step-8 review prompt
- [ ] ait monitor: agent cards show `phase:` beside `gates:` on the status row
- [ ] Spawn a shadow with `e` from minimonitor: aitask_shadow_capture.sh --phase returns VIA:pane-option IMMEDIATELY after spawn, before the first refresh tick
- [ ] Spawn a shadow with `e` from the FULL monitor: same — VIA:pane-option before the first tick (this surface was missed in the first implementation pass)
- [ ] The stamped @aitask_shadow_phase value UPDATES after the followed agent advances a checkpoint (it must not stay at its launch value)
- [ ] Shadow offers the phase-driven default for a bare "review this", names the phase and its evidence, and states how to override; asking explicitly for the OTHER analysis still runs it
- [ ] An agent parked at an AskUserQuestion now shows as awaiting input in both ait monitor and ait minimonitor (before t1420 it read as idle)
- [ ] Answer a checkpoint, then trigger a tool-permission prompt: the phase follows the LEDGER, not the answered checkpoint still visible in scrollback

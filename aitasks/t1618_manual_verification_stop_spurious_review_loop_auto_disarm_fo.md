---
priority: medium
effort: medium
depends: [1606]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1606]
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-25 22:35
updated_at: 2026-08-25 22:35
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1606

## Verification Checklist

- [ ] Arm the loop (L) against a live Claude followed agent with a Codex shadow; let one recheck fire and confirm it is delivered and submitted as before.
- [ ] Confirm `ait minimonitor --loop-log` prints that session's events as decoded prose, newest first, naming the followed/shadow pair.
- [ ] Confirm a session file appeared under ~/.config/aitasks/review_loop_events/ with mode 0600 in a 0700 directory.
- [ ] Provoke a Codex exec-approval dialog during a recheck delivery: the loop must HOLD with the banner "holding: shadow showed a dialog - will retry" and stay ARMED, not disarm.
- [ ] Confirm the held loop recovers on its own once the dialog is answered, and the banner returns to the armed/fired line.
- [ ] Press L to disarm and L again to re-arm during a delivery drain: the fresh arm must survive, with no "recheck text left in the shadow composer" toast.
- [ ] Re-arm onto a DIFFERENT shadow pane, then force an immediate disarm; confirm the recorded event names the new pair, not the previous one.
- [ ] Kill the shadow pane while armed: confirm the toast and the recorded reason say "the shadow pane is gone" (not the old shared "followed agent or shadow pane is gone").
- [ ] Kill the followed agent pane while armed: confirm it says "the followed agent's pane is gone" - the other half of the pair that shared one message before t1606.
- [ ] Verify the hold banner renders within 2 rows at a 40-column minimonitor pane and does not cost the pane list a row.
- [ ] Run `ait minimonitor --loop-log` from inside the window that already hosts a minimonitor: it must print events, not "A monitor is already running".
- [ ] Re-run t1523 item #4 against a real Codex pane - the end-to-end delivery proof no in-suite test can supply.

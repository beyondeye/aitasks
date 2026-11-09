---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [monitor, minimonitor]
verifies: [2246]
premise_baseline: eaa6af1abe9037b1ecc23e3f108816e67d9c7d20 @ 2026-11-09 11:54
anchor: 2034
followup_kind: risk_mitigation
created_at: 2026-11-09 11:54
updated_at: 2026-11-09 11:54
---

## Origin

Risk-mitigation ("after") follow-up for t2246, created at Step 8d after implementation landed.

## Manual Verification Task

This task is handled by the manual-verification module. Run
`/aitask-pick <id>` and the workflow dispatches to the interactive checklist
runner. Each item below must reach a terminal state (Pass / Fail / Skip)
before the task can be archived. Defer is allowed, but it creates a
carry-over task.

## Risk addressed

The risk is that the restart misbehaves against the real pre-change server,
that the agent-sitrep window still lists more than the agent, or that the
upgrade hook reaches outside its tree. The matching `## Risk` bullet:

- The user-visible fix (SIGTERM-retire the 2026-11-06 server, then one item in
  the `agent-sitrep` minimonitor) and the upgrade-hook scoping can only be
  confirmed live · severity: medium · → mitigation: sitrep_window_live_check

## Goal

Confirm live that t2246's restart procedure works: against the real
pre-change server, in the agent-sitrep window, and through a real
`ait upgrade`.

## Verification Checklist

- [ ] `ait monitor --server-status` lists this tmux server's status server with its pid, start time, version and script (before the restart, the 2026-11-06 server, pid 3870908, if it is still running)
- [ ] `ait monitor --restart-server` prints RETIRED:<sock>|pid=<old>, then STARTED:<sock>|<new> (or RUNNING), then REPLACEMENT:<sock>|pid=<new>|version=0.40.1, and exits 0
- [ ] Open monitor and minimonitor TUIs reconnect to the fresh server automatically, with no TUI restart and no lasting red "control: fallback" / "rc:fb" badge
- [ ] The agent-sitrep window's minimonitor lists exactly one item (the sitrep agent); the sitrep TUI pane is absent from both the monitor and the minimonitor lists
- [ ] A real `ait upgrade` (or a scratch install run twice) prints MONITOR_SERVER:RETIRED: only for servers started from the upgraded project; `ait monitor --server-status` shows other projects' servers unchanged
- [ ] `ait monitor --help` lists --restart-server and --server-status

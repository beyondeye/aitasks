---
priority: medium
effort: medium
depends: [1465]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1465]
followup_kind: manual_verification
created_at: 2026-08-10 13:42
updated_at: 2026-08-13 23:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1465

## Verification Checklist

- [ ] Launch an agent on a task from `ait board` (not from a shell): the resulting lock's `pid:` equals that agent window's `#{pane_pid}`, and `pid_starttime_kind:` is `proc`
- [ ] Kill the agent's tmux pane mid-task, then re-pick the same task: the crash-recovery prompt appears and names the dead PID (this is the RECLAIM_CRASH wording a human has to read as truthful)
- [ ] Re-pick a task that a second, still-running agent pane already holds: NO crash is claimed — the prompt must be the anomaly wording, not "appears to have crashed"
- [ ] Start an agent outside tmux (plain terminal) and claim a task: the lock records `pid: -`, the claim still succeeds, and a later re-pick reports the anomaly path rather than a crash
- [ ] Set `AIT_AGENT_PID` to a stale/dead PID when launching, and confirm the "does not name a live process" warning is actually visible in the agent's terminal (it is forwarded to stderr through aitask_pick_own.sh)
- [ ] Check `ait lock --list` and `ait lock --check <id>` still render correctly with the new `pid_starttime_kind:` field present in the lock YAML
- [ ] Confirm the board's lock indicators still resolve for locks written by the new writer (the lock parser reads locked_by/locked_at/hostname; the added field must not disturb it)

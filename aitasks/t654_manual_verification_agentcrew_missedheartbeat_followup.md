---
priority: medium
effort: medium
depends: [652]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [652]
created_at: 2026-04-26 14:26
updated_at: 2026-04-26 14:26
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t652

## Verification Checklist

- [ ] Run `ait crew dashboard --crew <id>` with an agent in MissedHeartbeat and verify the row renders in the new yellow (#F1FA8C) — distinct from Paused orange and Error red.
- [ ] Smoke test: init a crew with heartbeat_timeout_minutes=1, start runner, mark an agent Running, let heartbeat go stale, and confirm two consecutive runner iterations transition Running -> MissedHeartbeat -> Error.
- [ ] Recovery smoke: while an agent is in MissedHeartbeat, run `ait crew status heartbeat --crew X --agent Y` and confirm the next runner iteration flips it back to Running and clears missed_heartbeat_at.
- [ ] Direct Error->Completed via CLI: `ait crew status set --crew X --agent Y --status Error` then `... --status Completed` — confirm STATUS_SET output and that crew rollup recomputes correctly.
- [ ] Capacity guard: with max_concurrent=1 and a Running agent that goes MissedHeartbeat, confirm the runner does NOT launch a second agent (count_running treats MissedHeartbeat as a held slot).

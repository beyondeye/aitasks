---
priority: medium
effort: medium
depends: [1748]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1748]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-09 13:00
updated_at: 2026-09-09 13:43
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1748

## Verification Checklist

- [ ] [t1748] Run /aitask-pick on any task under the fast profile; confirm the plan-externalization commit reaches aitask_task_commit.sh and reports COMMITTED:, with no permission prompt.
- [x] [t1748] Abort a task whose plan was never externalized (task-abort.md); confirm the agent reports the optional SKIPPED:unknown:<plan_file> correctly and does not read exit 0 as a partial failure. — PASS 2026-09-09 13:43 auto: real helper in isolated scratch repo emitted SKIPPED:unknown:aiplans/p99_probe.md then COMMITTED:1 at exit 0, committing only the task file; negative control (required task file missing) also exits 0 with COMMITTED:, proving task-abort.md's per-path required/optional rule is necessary and discriminating
- [ ] [t1748] With a second session holding staged task-data files, run a converted site; confirm git show --name-only on the resulting commit lists only this task's paths.
- [defer] [t1748] Confirm aitask_task_commit.sh runs without a permission prompt under the Codex and OpenCode trees — touchpoints 3, 6 and 7 were written but only the Claude one (touchpoint 1) was exercised during t1748. — DEFER 2026-09-09 13:43 auto: touchpoints 1/3/4/6/7 all carry the entry (audit-helper-whitelist empty; entries read directly), but no available Codex surface discriminates -- codex exec v0.153.4 runs at approval:never and a forced decision=prompt control for the same command ran anyway, and interactive -a offers only on-request/never; OpenCode has no live config in this repo (touchpoint 7 is seed-only), so it needs a freshly seeded project

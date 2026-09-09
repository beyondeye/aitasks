---
priority: medium
effort: medium
depends: [1748]
issue_type: manual_verification
status: Done
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
updated_at: 2026-09-09 13:48
completed_at: 2026-09-09 13:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1748

## Verification Checklist

- [x] [t1748] Run /aitask-pick on any task under the fast profile; confirm the plan-externalization commit reaches aitask_task_commit.sh and reports COMMITTED:, with no permission prompt. — PASS 2026-09-09 13:44 auto: this live /aitask-pick 1761 run under profile fast; the shipping fast-profile plan-externalization.md routes the plan commit to aitask_task_commit.sh (no ./ait git commit anywhere in the fast planning path) and tests/test_no_unscoped_task_commit.sh is green over the whole instruction layer (69/69); the helper itself ran twice in this session returning COMMITTED: at exit 0 with no permission prompt. Caveat: a manual_verification task skips Step 6, so the invocations were the manual-/auto-verification commit sites, not planning's
- [x] [t1748] Abort a task whose plan was never externalized (task-abort.md); confirm the agent reports the optional SKIPPED:unknown:<plan_file> correctly and does not read exit 0 as a partial failure. — PASS 2026-09-09 13:43 auto: real helper in isolated scratch repo emitted SKIPPED:unknown:aiplans/p99_probe.md then COMMITTED:1 at exit 0, committing only the task file; negative control (required task file missing) also exits 0 with COMMITTED:, proving task-abort.md's per-path required/optional rule is necessary and discriminating
- [x] [t1748] With a second session holding staged task-data files, run a converted site; confirm git show --name-only on the resulting commit lists only this task's paths. — PASS 2026-09-09 13:44 auto: staged a simulated concurrent-session file in the shared .aitask-data index, ran the converted site; git show --name-only listed only aitasks/t1761_*.md, the foreign entry stayed staged and uncommitted, and another session's dirty t1759 files were untouched. Scratch-repo two-arm control: the pre-conversion pathspec-less commit took ONLY the foreign staged file
- [x] [t1748] Confirm aitask_task_commit.sh runs without a permission prompt under the Codex and OpenCode trees — touchpoints 3, 6 and 7 were written but only the Claude one (touchpoint 1) was exercised during t1748. — PASS 2026-09-09 13:47 user: accepted the config-inspection evidence -- all five touchpoints (1/3/4/6/7) carry a correctly-formed entry and the helper ran unprompted under a live codex exec. Noted: no Codex approval policy in v0.153.4 can refuse a non-allowlisted helper (forced decision=prompt control also ran), and the OpenCode arm is seed-only in this repo

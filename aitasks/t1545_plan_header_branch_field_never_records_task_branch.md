---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [task_workflow, git, worktree, claudeskills]
gates: [risk_evaluated]
anchor: 1536
followup_kind: upstream_defect
created_at: 2026-08-17 17:38
updated_at: 2026-08-17 17:38
---

## Origin

Spawned from t1536 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_plan_externalize.sh:716-718` — the `Branch:` header
  field is derived from the repo root's `git symbolic-ref --short HEAD` and is
  suppressed when it equals the primary branch. In worktree mode the helper
  always runs from the repo root, so this field can never record the task's own
  `aitask/<task_name>` branch — it is either absent or reports an unrelated
  branch that happens to be checked out at the root.

## Diagnostic context

Surfaced while auditing every producer and consumer of the plan metadata header
for t1536 (which replaced the `Worktree:` directory probe with caller-supplied
`--worktree` intent). `Worktree:`, `Base branch:` and `Output branch:` are all
now intent-driven and validated; `Branch:` is the one field still derived from
ambient process state.

The defect is **pre-existing and independent of t1536**: deferring the fork does
not change what `current_branch` observes, because externalization ran from the
repo root before the change and still does. The t1536 consumer audit found no
code path that reads `Branch:` back, so nothing is currently broken by it — the
field is misleading documentation rather than an active fault.

## Suggested fix

Decide the field's contract and make it match one of:

1. **Intent-driven, like its siblings** — record `aitask/<task_name>` when the
   caller passes `--worktree`, since that is the branch the task will actually
   be implemented on. This makes the header self-consistent.
2. **Remove it** — if no consumer needs it, dropping the field is simpler than
   fixing it. Check `crash-recovery.md`, `merge-target-sync.md` and Step 9's
   merge pre-flight first; the t1536 audit found none, but re-verify.

Either way, add a test case to `tests/test_plan_externalize.sh` alongside the
existing `Worktree:` / `Base branch:` / `Output branch:` header assertions.

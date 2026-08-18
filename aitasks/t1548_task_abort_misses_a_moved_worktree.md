---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: [1536]
issue_type: bug
status: Implementing
labels: [task_workflow, git, worktree, claudeskills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1536
followup_kind: review_finding
implemented_with: claudecode/opus5
created_at: 2026-08-17 17:40
updated_at: 2026-08-18 11:06
---

## Origin

Spawned from t1536 review (finding 4, disposition: follow-up). `depends: [1536]`
is set because the moved-worktree support this reconciles with only exists as of
t1536.

## Problem

t1536's Step 7 "Deferred worktree fork" block resolves a reusable worktree
record-aware — it reads the `worktree <path>` line of the porcelain record whose
`branch` is `refs/heads/aitask/<task_name>` — so a worktree that was moved out of
`aiwork/<task_name>` is still found and worked in correctly.

The **Task Abort Procedure** (`.claude/skills/task-workflow/task-abort.md`) did
not follow: it removes only the hardcoded conventional path.

```bash
git worktree remove aiwork/<task_name> --force 2>/dev/null || true
rm -rf aiwork/<task_name> 2>/dev/null || true
git branch -d aitask/<task_name> 2>/dev/null || true
```

After a moved-worktree resume all three are no-ops — the first two miss the real
directory, and `git branch -d` then fails because the branch is still checked out
in the surviving worktree. The `2>/dev/null || true` guards (which exist so that
an abort reached *before* the fork is quiet) swallow every one of those failures,
so the user is told the task was aborted while the worktree and branch remain.

## What already landed in t1536

Honesty only: the procedure now requires re-running the record-aware extraction
after the removal commands and, if a path is still reported, naming it instead of
reporting a clean abort. The cleanup itself is still wrong.

## Suggested fix

Pick one and make the docs and behaviour agree:

1. **Resolve, then remove.** Extract the record's real path first and pass it to
   `git worktree remove` / `rm -rf`, then delete the branch. Reuse the same awk
   extraction the Step 7 fork block uses rather than writing a second one —
   consider lifting it into a shared snippet so the two cannot drift.
2. **Narrow the contract.** Declare that a framework-managed worktree must live
   at `aiwork/<task_name>`, and make the Step 7 reuse path reject (or relocate)
   anything else, so abort's hardcoded path is correct by construction.

Option 1 preserves the flexibility t1536 introduced; option 2 removes it. Either
is defensible — what is not defensible is the current split, where one half of
the framework supports moved worktrees and the other half silently does not.

## Verification

Reproduce first: create a task worktree, `git worktree move` it, then run the
abort commands and confirm the worktree and `aitask/<task_name>` branch both
survive while the procedure would otherwise report success.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-18T08:06:27Z status=pass attempt=1 type=human

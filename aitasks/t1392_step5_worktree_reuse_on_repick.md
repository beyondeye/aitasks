---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [task_workflow, claudeskills]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-03 16:52
updated_at: 2026-08-17 17:40
boardidx: 26624
---

## Problem

`task-workflow` **Step 5** ("If Yes" branch) unconditionally runs:

```bash
git worktree add -b aitask/<task_name> aiwork/<task_name> <base-branch>
```

It has no reuse check. **Re-entry Routing** already has one — "If a worktree for
`<task_name>` already exists — `git worktree list --porcelain` shows a
`branch refs/heads/aitask/<task_name>` line — reuse it (work in that directory);
do **NOT** recreate the branch/worktree." — but the plain Step 5 path does not.

So on any profile with `create_worktree: true`, a task that was picked, got its
worktree created, and was then **stopped** (rather than aborted) fails on
re-pick: the branch and worktree still exist, and `git worktree add -b` errors.

## How it is reached

Every "stop, don't abort" exit leaves the worktree in place by design (only the
**Task Abort Procedure** removes it). All of these reach it:

- `planning.md` Checkpoint → "Approve and stop here"
- `remote-drift-check.md` → "Stop and re-verify plan"
- Step 7's risk-mitigation "before" stop (task reverted to `Ready`, blocked on
  the mitigation)

Each reverts the task to `Ready`, so the re-pick fails Step 3 Check 5's
`Implementing` status gate, skips Re-entry Routing (and its reuse rule), and
lands in plain Step 5.

## Why it has not bitten yet

Neither shipped profile that records gates creates worktrees: `fast.yaml` sets
`create_worktree: false` and `remote.yaml` never worktrees. It is reachable only
on a user-authored worktree profile.

## Origin

Surfaced while implementing t1380, which added a **third** way to reach the stop
path (the drift check on the `IMPLEMENT` re-entry route) and therefore made this
pre-existing hole more reachable. Deliberately left out of t1380's scope — it is
outside that task's acceptance criteria and deserves its own plan and tests.

## Suggested fix

Add the same one-sentence reuse rule Re-entry Routing already carries to Step 5's
"If Yes" branch, immediately before the `git worktree add` block. Consider
deriving both from one shared sentence rather than stating it twice — a second
copy is exactly the drift shape t1380 was fixing.

## Acceptance criteria

- [ ] Step 5's "If Yes" branch reuses an existing `aitask/<task_name>` worktree
      instead of failing.
- [ ] The rule is stated once, not duplicated between Step 5 and Re-entry
      Routing (or a guard pins the two copies in agreement).
- [ ] A test covers pick → "Approve and stop here" → re-pick on a
      `create_worktree: true` profile, and is proven to fail before the fix.
- [ ] Goldens regenerated in the same commit; `aitask_skill_verify.sh` passes.

## Key files

- `.claude/skills/task-workflow/SKILL.md` — Step 5 "If Yes"; Re-entry Routing's
  existing "Environment setup (Step 5) with reuse" bullet
- `.claude/skills/task-workflow/plan-approved-stop.md` — the stop sequence that
  intentionally leaves the worktree in place

## Superseding context — read before planning this task (t1536)

**t1536_defer_worktree_fork_until_after_plan_approval** moves the
`git worktree add` out of Step 5 entirely: Step 5 keeps only the branch
*resolution*, and the fork runs at the top of **Step 7**, after plan approval and
after the Remote Drift Check clears.

That change dissolves two of the three reaching paths listed above:

- "Approve and stop here" — no worktree was ever created, nothing to collide with
- "Stop and re-verify plan" — same

Only **Step 7's risk-mitigation "before" stop** still leaves a real worktree
behind (the fork happens at the top of Step 7, the mitigation stop later within
it), so a reuse check is still needed — and t1536 carries it as its acceptance
criterion 4, applied at the new Step 7 fork site rather than at Step 5.

**Do not plan this task against Step 5 without first checking t1536's status.**
If t1536 has landed, this task's acceptance criteria are already satisfied and it
should be closed; if t1536 is still pending, the two must be sequenced (this one
would be re-written by t1536's move) rather than implemented in parallel.

## Resolution (closed by t1536)

Landed in `bbafbd4f5` — *enhancement: Defer the worktree fork until after plan
approval (t1536)*.

**The failing site no longer exists.** t1536 removed `git worktree add -b` from
Step 5 entirely: Step 5 now only *resolves* the branch context, and the fork
moved to the top of Step 7. The reuse check this task asked for was carried to
that new fork site as t1536's acceptance criterion 4, and it is record-aware —
it resolves the reusable directory from the `worktree <path>` line of the
matching porcelain record rather than assuming `aiwork/<task_name>`.

Two of the three reaching paths named above are **dissolved** rather than fixed:

- `planning.md` Checkpoint → "Approve and stop here"
- `remote-drift-check.md` → "Stop and re-verify plan"

Both stops now happen *before* the fork, so neither leaves a worktree to collide
with on re-pick. (`plan-approved-stop.md` was updated to say so.)

The third — Step 7's risk-mitigation "before" stop — still reaches a real
worktree, which is exactly why the reuse check was still required and was
implemented.

Nothing further to do here.

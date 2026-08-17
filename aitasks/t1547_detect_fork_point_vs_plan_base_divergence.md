---
priority: medium
effort: medium
depends: [1536]
issue_type: enhancement
status: Ready
labels: [task_workflow, git, worktree, claudeskills]
gates: [risk_evaluated]
anchor: 1536
created_at: 2026-08-17 17:40
updated_at: 2026-08-17 17:40
---

## Origin

Spawned from t1536, whose Non-goals said explicitly: "spin it off if the plan
confirms it is still reachable after this change." It is. `depends: [1536]` is
set because this task's entire premise is t1536's deferred fork.

## Problem

After t1536 the worktree fork happens at the top of Step 7, after the Remote
Drift Check returns "Continue anyway". Nothing compares the base HEAD the drift
check validated with the base HEAD `git worktree add` actually cuts from. Two
windows remain:

1. **The guard window.** The chosen fork site places the Step 7
   pre-implementation ownership guard between the drift check and the fork. That
   guard can prompt, refresh a lock, and commit/push task data — real wall-clock
   time with a human in the loop — and neither step locks `<base>`. A concurrent
   agent committing to `<base>` in the same repo advances the fork point after
   the check passed.

2. **Plan-vs-fork divergence, sign flipped.** Before t1536 the fork was *older*
   than the plan (cut in Step 5, plan written in Step 6). After t1536 the fork is
   *newer* (plan written in Step 6, branch cut in Step 7). Either way, nothing
   compares the tree the plan was designed against with the tree the branch is
   cut from. t1536 changed when the gap appears, not whether it exists.

The existing drift check does not cover this: it compares
`<branch>..origin/<branch>`, i.e. local-vs-remote, never fork-point-vs-current-base.

## Suggested shape

- Record `git rev-parse <base_branch>` into the workflow context at drift-check
  time (the value the user implicitly approved by choosing "Continue anyway").
- Re-read it immediately before `git worktree add` in the Step 7 fork block.
- When the two differ, surface the delta to the user (commit count and whether
  any of the new commits touch files the plan targets — `aitask_remote_drift_check.sh`
  already has the plan-overlap logic worth reusing rather than reimplementing)
  and let them choose to cut from the new base, cut from the approved SHA, or stop.

## Non-goals

- Locking the base branch. This is a detector, not a mutex.
- Re-cutting or rebasing an already-created worktree.

## Notes

Prefer extending `aitask_remote_drift_check.sh` with a flag over writing a
parallel comparison helper — see the "reuse the canonical seam" guidance in
CLAUDE.md's Reusable Helpers section.

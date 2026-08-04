---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [task_workflow, claudeskills]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-03 16:52
updated_at: 2026-08-03 16:52
boardidx: 27648
---

## Problem

**Step 9 never fetches.** Its merge pre-flight checks only that
`refs/heads/<output_branch>` exists locally and is not held by another worktree;
`git merge` is then a purely local operation. Verified: `grep -n "git fetch\|git
pull" .claude/skills/task-workflow/SKILL.md` returns nothing.

So when `origin/<output_branch>` has advanced past the local branch, the merge
**succeeds cleanly**, the local branch quietly diverges, and the problem only
appears later as a non-fast-forward push rejection — by which point the user is
outside the workflow and has to reconcile by hand.

t1380 added `.claude/skills/task-workflow/merge-target-sync.md`, which closes
exactly this gap (fetch via `aitask_remote_drift_check.sh --unsynced`, then a
fast-forward-only sync that refuses on real divergence), but wired it into
**Re-entry Routing's `POSTIMPL` route only** — the resumed path, where staleness
is most likely.

The same staleness affects **every** task's Step 9, not just resumed ones: a
long implementation session is plenty of time for the merge target to move.

## Why t1380 did not just wire it in

Running the pre-flight on every Step 9 adds a **network fetch and a possible
prompt to every task's merge** — a behaviour change for every user, in the same
class as the `record_gates`-for-`default` question t1380 also carved out. It
deserves its own decision rather than arriving as a side effect.

## Questions this task must answer

- Always, or only when a remote exists / the branch is behind? (The helper
  already returns silently for `NO_REMOTE` / `FETCH_FAILED` / `UP_TO_DATE`, so
  "always" may already be quiet enough in practice.)
- Should it be profile-gated (a new key), or unconditional?
- Where exactly — before the merge-approval `AskUserQuestion` (so the user
  decides once, informed) or after it (fewer prompts on the happy path)?
- Does the `POSTIMPL` route then become a plain no-op that defers to Step 9,
  removing the special case entirely? That would be the cleaner end state.

## Acceptance criteria

- [ ] A decision is recorded (in the plan and in
      `aidocs/gates/ledger-driven-reentry.md`) on always-vs-gated, with the
      user's confirmation — this is a UX change for every user.
- [ ] If wired in: Step 9 runs the pre-flight and the `POSTIMPL` special case is
      simplified or removed rather than left as a second call site.
- [ ] Behaviour with no remote / an unreachable remote is unchanged (silent).
- [ ] Tests cover the stale-target case end-to-end at Step 9, each proven to
      fail before the fix. `tests/test_remote_drift_check.sh` Test 12 already
      pins the underlying git behaviour (the gap, the fast-forward recovery, and
      the refusal on real divergence) and can be built on.
- [ ] Goldens regenerated in the same commit; `aitask_skill_verify.sh` passes.

## Key files

- `.claude/skills/task-workflow/SKILL.md` — Step 9 "Pre-flight the merge target",
  and Re-entry Routing's `POSTIMPL` route
- `.claude/skills/task-workflow/merge-target-sync.md` — the procedure to reuse
- `.aitask-scripts/aitask_remote_drift_check.sh` — the detector (`--unsynced`)
- `tests/test_remote_drift_check.sh` — Test 12

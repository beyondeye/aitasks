---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [contribution, ait_setup, installation]
assigned_to: dario-e@beyond-eye.com
issue: https://github.com/beyondeye/aitasks/issues/10
created_at: 2026-04-26 12:17
updated_at: 2026-04-26 12:18
---

Issue created: 2026-04-26 12:14:17, last updated: 2026-04-26 12:14:28

## `ait setup`: stop and require acknowledgment when no git remote is configured (lock infra cannot be pushed)

## Summary

`ait setup` should detect when the local git repo has no `origin` remote configured.
When run in that state, it cannot push the orphan `aitask-locks` branch to the remote,
so subsequent task locking silently breaks. Setup should stop, warn the user, and
require an explicit acknowledgment to continue.

## Symptom

Running `/aitask-pick <task>` fails with:

```
LOCK_ERROR:fetch_failed
```

`./.aitask-scripts/aitask_lock_diag.sh` reports:

```
--- 3. Lock branch ---
  FAIL: Lock branch 'aitask-locks' not found on remote
        Run 'ait setup' to initialize
--- 4. Fetch ---
  FAIL: Failed to fetch lock branch
        Network issue or branch not initialized
```

## Root cause

`ait setup` was run **before** `git remote add origin <url>`. The setup script created
the `aitask-locks` orphan branch in the local clone but had no remote to push it to,
so the branch never propagated. Re-running `ait setup` after adding the remote fixes
it (or `./.aitask-scripts/aitask_lock.sh --init` does the same), but the user has no
way to know they need to.

## Proposed fix (primary)

During `ait setup`, before any lock-infra step:

1. Run `git remote get-url origin` (or equivalent).
2. If no remote exists:
   - Print a clear warning: lock infrastructure cannot be initialized without a remote.
     The `aitask-locks` orphan branch needs a remote to be useful for cross-machine
     coordination.
   - Tell the user the fix: `git remote add origin <url>` then re-run `ait setup`.
   - Prompt `Acknowledge (Y/n)` before proceeding.
   - On acknowledgment, skip the lock-init step (don't create a local-only orphan
     branch that will never be pushed) and continue with the rest of setup.

## Related observations (secondary fixes worth folding in)

1. **`aitask_lock.sh` conflates two different failure modes.** Lines 111-112:

   ```bash
   if ! git fetch origin "$BRANCH" --quiet 2>/dev/null; then
       die_code 11 "Failed to fetch '$BRANCH' from origin. Run 'ait setup' to initialize."
   fi
   ```

   This emits exit code 11 (`fetch_failed`, mapped to `LOCK_ERROR:fetch_failed`) for
   both "branch does not exist on remote" and "fetch genuinely failed" (network /
   auth / etc). A `git ls-remote --exit-code origin "$BRANCH"` probe before the fetch
   would let it return exit code 10 (`LOCK_INFRA_MISSING`) in the first case, which
   the workflow already documents a handler for ("Inform user to run `ait setup` and
   abort"). Same pattern applies to lines 200-201, 248, 273, 311.

2. **`aitask_lock_diag.sh` already distinguishes the two cases correctly** ("Lock
   branch not found on remote" vs "Failed to fetch lock branch"). The diagnosis logic
   exists — it just needs to be ported into the lock + setup hot paths.

## Context

Hit while running `/aitask-pick 10_2` on a downstream project (`aitasks_mobile`) using
the framework as a clone. Diagnosis was straightforward thanks to `lock_diag.sh`, but
a less experienced user would have been stuck.
## Comments

**github-actions** (2026-04-26 12:14:28)

## Contribution Overlap Analysis

No overlapping contribution issues found for #10.

<!-- overlap-results overlap_check_version: 1 -->

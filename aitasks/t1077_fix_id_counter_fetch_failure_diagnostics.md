---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitasks, task-management, git]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-26 07:40
updated_at: 2026-06-28 10:45
boardidx: 220
---

## Problem

`aitask_create.sh --batch --commit` can fail to create a parent task with a misleading atomic-ID error even when `ait setup` has already initialized the counter branch correctly.

Observed failure from another repo:

```text
Error: Atomic ID counter failed: Pushed local counter branch to remote (auto-upgrade)
Pushed local counter branch to remote (auto-upgrade)
Pushed local counter branch to remote (auto-upgrade)
Pushed local counter branch to remote (auto-upgrade)
Pushed local counter branch to remote (auto-upgrade)
Error: Failed to claim task ID after 5 attempts. Try again later.
Run 'ait setup' to initialize the counter.
```

The counter was actually healthy:

- `aitask-ids` and `origin/aitask-ids` existed.
- local and remote refs pointed to the same commit after diagnosis.
- `next_id.txt` matched the highest archived/active task plus one.
- a direct `aitask_claim_id.sh --debug --claim` later succeeded.

The likely root cause was that `git fetch origin aitask-ids --quiet` failed for an environmental reason, such as an execution sandbox being unable to write `.git/FETCH_HEAD`. The claim script suppressed the real fetch stderr, treated any fetch failure as "remote branch is missing", attempted local-to-remote auto-upgrade, repeated that five times, and finally returned a misleading setup/counter initialization message.

## Motivation

This failure mode wastes task IDs, blocks automation, and sends the user toward `ait setup` even when setup is not the problem. It also hides the actionable cause, such as a `.git/FETCH_HEAD` write failure, network/auth failure, or other git fetch error.

The ID assignment code should distinguish:

- remote counter branch is absent and should be initialized or auto-upgraded;
- remote branch exists but fetch failed for a real git/environment reason;
- push failed because of a legitimate compare-and-swap race;
- local/remote counter refs are divergent or stale.

## Proposed Fix

Update `.aitask-scripts/aitask_claim_id.sh`:

- Capture `git fetch origin "$BRANCH"` stderr instead of discarding it.
- Before running `try_push_local_to_remote`, confirm the remote branch is absent with `git ls-remote --heads origin "$BRANCH"`.
- If the remote branch exists but fetch fails, fail immediately with the captured fetch error rather than entering the auto-upgrade loop.
- Improve push-failure diagnostics by capturing push stderr and distinguishing non-fast-forward races from auth/network/permission failures where possible.
- In `try_push_local_to_remote`, avoid printing `Pushed local counter branch to remote (auto-upgrade)` when the branch already exists and the push is merely up-to-date.
- Consider using an explicit refspec fetch, for example `refs/heads/aitask-ids:refs/remotes/origin/aitask-ids`, if that is more robust across git versions/configurations.

Update `.aitask-scripts/aitask_create.sh`:

- Stop appending `Run 'ait setup' to initialize the counter` to every claim failure.
- Preserve the lower-level claim error verbatim.
- Only suggest `ait setup` when the claim script specifically reports that the counter branch is missing/uninitialized.

## Acceptance Criteria

- If `origin/aitask-ids` exists but `git fetch` fails, task creation reports the real fetch error and does not attempt auto-upgrade.
- If `origin/aitask-ids` is absent and a local `aitask-ids` branch exists, auto-upgrade still works.
- If a real ID-claim race occurs, retry behavior remains intact.
- Batch task creation surfaces useful, non-misleading diagnostics.
- Add a regression test or script-level test case that simulates fetch failure with an existing remote branch and verifies no auto-upgrade loop occurs.

## Coordination — t1079 (counter-drift correctness)

t1079 (`harden_task_id_assignment_against_counter_drift`) is the **correctness
counterpart** to this task: same file (`aitask_claim_id.sh`), different bug. This
task fixes misleading *fetch-failure diagnostics / error messaging*; t1079 fixes
the *drift / duplicate-ID invariant* (counter falling below `max(task ids)` and
handing out duplicates — observed live 2026-06-25/26). Implement coherently since
both touch the claim path. See t1079.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-28T07:44:59Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-28T07:45:00Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-28T07:52:56Z status=pass attempt=1 type=human

---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_pick, task_workflow, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-28 09:54
updated_at: 2026-04-28 09:56
---

## Symptom

Running `/aitask-pick 688` from one PC silently succeeded even though task t688 was already locked **by the same user** on a different PC and had status `Implementing`. No warning, no confirmation prompt — the workflow proceeded straight to Step 5 (worktree/branch setup) and Step 6 (planning) as if it were a fresh pick. Expected behavior: a clear warning + `AskUserQuestion` confirming whether to reclaim.

## Root cause (single bug, multiple layers reinforcing the silence)

1. **`.aitask-scripts/aitask_lock.sh:156-163` — same-email re-lock is a silent "refresh".** When the existing lock's `locked_by` field matches the email of the new claimant, the lock is overwritten without complaint:
   ```bash
   if [[ "$locked_by" == "$email" ]]; then
       debug "Lock already held by same user, refreshing"
   else
       echo "LOCK_HOLDER:..."
       die "Task t$task_id is already locked by ..."
   fi
   ```
   Although the lock YAML stores `hostname:` (set via `get_hostname()` at line 171), the script never compares it against the current host. So a same-user-different-PC reclaim is indistinguishable from an idempotent same-PC re-lock.

2. **`.aitask-scripts/aitask_pick_own.sh:222-232, 305` — `update_task_status` is unconditional.** It runs `aitask_update.sh --status Implementing` regardless of the task's existing status. There is no read of the prior status and no signal emitted when the task was already in `Implementing` before this pick attempt.

3. **`.claude/skills/task-workflow/SKILL.md` Step 4 (lines 137-164) — no read of task status before claim.** The only `AskUserQuestion` Step 4 surfaces is on `LOCK_FAILED`, which by construction only fires for a *different* email. The same-user-different-PC case never trips a prompt.

4. **`.claude/skills/task-workflow/SKILL.md` Step 7 pre-implementation guard (lines 228-245) actively masks re-picks.** When `status == Implementing` AND `assigned_to == current email`, it says "Ownership was already acquired in Step 4. Proceed normally." This guard was designed for the plan-mode-deferred-Step-4 case, but it makes a multi-PC reclaim indistinguishable from same-session continuation.

## Proposed fix

### Layer 1: `aitask_lock.sh`

Detect same-user-different-host re-lock as a non-silent event. When `locked_by == email` but `locked_hostname != $(get_hostname)` (or `locked_at` is older than some threshold, e.g. >1h), emit a structured signal **in addition** to refreshing the lock — so the caller can decide whether to surface a prompt. Suggested form:

```
LOCK_RECLAIM:<prev_hostname>|<prev_locked_at>|<current_hostname>
```

Then continue with the refresh as today (do not `die`, since same-user re-lock is still legal — but now the caller can prompt).

### Layer 2: `aitask_pick_own.sh`

- Read the task's current `status` before calling `aitask_lock.sh`. If it is already `Implementing` and `assigned_to` matches the new claim email, emit:
  ```
  RECLAIM:<prev_status>|<prev_assigned_to>|<prev_hostname>|<prev_locked_at>
  ```
  Either alongside `OWNED:` or replacing `OWNED:` with a distinct success code that the caller treats as "needs confirmation".
- Plumb the `LOCK_RECLAIM:` signal from layer 1 through to the caller (it's currently discarded).

### Layer 3: `task-workflow/SKILL.md` Step 4

Add a new branch to the output-parsing list:

> - `RECLAIM:<prev_status>|<prev_assigned_to>|<prev_hostname>|<prev_locked_at>` — Task is already in `Implementing` by you on `<prev_hostname>` (since `<prev_locked_at>`). Use `AskUserQuestion`:
>   - Question: "Task t<N> is already in Implementing, claimed by you on `<prev_hostname>` (since `<prev_locked_at>`). Reclaim and continue here?"
>   - Header: "Reclaim"
>   - Options:
>     - "Reclaim and continue" — proceed; treat the existing `Implementing` status as resumed work.
>     - "Pick a different task" — abort the pick, return to Step 1.

### Layer 4: `task-workflow/SKILL.md` Step 7 guard

Tighten the same-user fast-path so it only suppresses the warning when the *current* host already holds the lock. Read the lock YAML `hostname:` (`./.aitask-scripts/aitask_lock.sh --check <task_id>`) and compare against `hostname` of the running shell. If they differ, fall through to the explicit reclaim prompt instead of silently proceeding.

## Verification

Manual reproduction:
1. On PC A, run `/aitask-pick <N>` and let it set the task to `Implementing` (do not finish).
2. From PC B (same user/email), run `/aitask-pick <N>`.
3. Confirm: an `AskUserQuestion` appears warning that the task is already `Implementing` on PC A (with `locked_at` and `hostname`), offering "Reclaim and continue" / "Pick a different task".
4. Confirm "Pick a different task" returns to Step 1 without modifying the lock or task status.
5. Confirm "Reclaim and continue" refreshes the lock to PC B (new `hostname:` in the lock YAML on the `aitask-locks` branch) and proceeds.

Automated tests:
- Add `tests/test_lock_reclaim_self_different_host.sh`: prime the lock branch with a YAML that has a fake hostname, call `aitask_lock.sh --lock` with the same email, assert the new `LOCK_RECLAIM:` line is present in stdout.
- Add `tests/test_pick_own_reclaim_signal.sh`: pre-set the task file to `status: Implementing` + `assigned_to: <email>`, call `aitask_pick_own.sh <id> --email <email>`, assert `RECLAIM:` is present.

## Out of scope

- Stale-lock auto-expiry (`aitask_lock.sh --cleanup` handles archived tasks; time-based expiry of live locks is separate).
- Cross-user lock takeover UX (already handled by the existing `LOCK_FAILED` + force-unlock prompt).

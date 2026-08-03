---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: []
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus5
created_at: 2026-08-02 21:31
updated_at: 2026-08-03 10:22
---

## Origin

Spawned from t1269 during Step 8b review. t1269 made `task_sync()` report failed
pulls instead of returning 0 silently; this neighbouring call site — one line
below it in the same function — was deliberately left out of its scope.

## Upstream defect

- `.aitask-scripts/aitask_pick_own.sh:143` — stale-lock cleanup failures are
  swallowed (`"$SCRIPT_DIR/aitask_lock.sh" --cleanup 2>/dev/null || true`), so
  `aitask_lock.sh --cleanup` can fail on every pick with zero signal. Same
  silent-failure class as the `task_push` bug fixed in t1265 and the
  `task_sync` bug fixed in t1269, in the sibling statement.

## Diagnostic context

`sync_remote()` is the pre-task-selection step every pick / explore / fold /
review / pr-import runs:

```bash
sync_remote() {
    task_sync
    "$SCRIPT_DIR/aitask_lock.sh" --cleanup 2>/dev/null || true
}
```

t1269 rewrote line 142 (`task_sync`) to classify its failure, expose
`TASK_SYNC_*` globals, warn on stderr, and surface `SYNC_FAILED:<reason>` from
`aitask_pick_own.sh --sync`. Line 143 was left untouched: both its stderr and
its exit status are discarded, so a failed stale-lock sweep is
indistinguishable from a successful one.

The consequence is the mirror image of the bug t1269 fixed. Lock cleanup is
what releases locks abandoned by dead sessions; if it silently fails (lock
branch unreachable, fetch failure, malformed lock record), stale locks
accumulate and the next pick reports `LOCK_FAILED` for a task nobody is
actually working on — pushing the user toward a force-unlock they should not
need. On a shared checkout, the same dirty-data-worktree condition that
permanently blocks `task_sync` is a plausible common cause for both.

## Suggested fix

- Decide the contract first: `--cleanup` is best-effort (it must never block a
  pick), so mirror the t1265/t1269 shape rather than letting it fail the script
  — capture the output, classify the failure, and warn only when locks were
  actually left uncleaned.
- Check what `aitask_lock.sh --cleanup` already reports on stderr and via its
  exit status before designing the seam; it may already distinguish "nothing to
  clean" from "could not read the lock branch", in which case the fix is just
  to stop discarding it.
- Reuse `_task_push_classify` / `_task_push_reason_hint` from
  `task_utils.sh` if the failure modes overlap (unreachable remote, dirty
  worktree) rather than forking a second classifier; `_task_push_reason_hint`
  takes an optional retry-command argument for exactly this kind of reuse.
- Keep the silence policy of its siblings: warn only when something is actually
  at risk, since this runs on every pick. Pin the silent paths with
  empty-stderr negative controls, as `tests/test_task_push.sh` does.

## Verification

- A `--cleanup` failure (unreachable lock branch) emits a warning naming what
  was left uncleaned, while `aitask_pick_own.sh` still exits 0 and the pick
  proceeds.
- A successful cleanup, and a cleanup with nothing to do, stay silent
  (negative controls).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T07:22:14Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-03T07:51:26Z status=pass attempt=1 type=human

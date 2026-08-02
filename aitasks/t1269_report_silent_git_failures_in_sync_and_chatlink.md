---
priority: medium
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
created_at: 2026-07-27 23:08
updated_at: 2026-08-02 10:01
boardidx: 210
---

## Origin

Spawned from t1265 during Step 8b review. t1265 made `task_push` report failed
pushes instead of exiting 0 silently; these two call sites of the same
silent-failure class were deliberately left out of its scope.

## Upstream defect

- `.aitask-scripts/lib/task_utils.sh:181-188` — `task_sync()` swallows
  `pull --rebase` failures (`2>/dev/null || true`) and returns 0, so a failed
  sync is indistinguishable from a successful one. Same defect class as the
  `task_push` bug fixed in t1265, in the sibling function.
- `.aitask-scripts/chatlink/task_create.py:120-129` — the
  `audit.warning("task push failed (rc=%s) ...")` branch is unreachable:
  `ait git push` always exits 0 by contract, so a failed push after chat-intake
  task creation is never logged and the commit silently stays local.

## Diagnostic context

t1265's root cause was that `task_push` retried, gave up, and `return 0` with
both helpers' stderr discarded — a completely failed push was byte-for-byte
indistinguishable from a successful one. Fixing it surfaced two neighbours of
the same shape:

- `task_sync()` was read while adding the `_ait_data_git` seam. It has the
  identical `2>/dev/null || true` swallow and no outcome reporting at all.
- `chatlink/task_create.py` was read while designing the cross-process outcome
  contract: it shells out to `ait git push`, captures output, and branches on
  `returncode != 0` — a condition that cannot occur.

## Suggested fix

- `task_sync()`: mirror t1265's shape — classify the failure, expose the
  outcome (the `TASK_SYNC_*` globals equivalent), and warn when local commits or
  remote commits are left unreconciled. Reuse `_task_push_classify` /
  `_task_push_reason_hint` from `task_utils.sh` rather than forking them.
- `chatlink/task_create.py`: pass `--batch` in the default `push_argv` and parse
  the structured line (`PUSHED` / `NOTHING` / `NO_REMOTE` / `FAILED:<reason>:<count>`),
  auditing a warning on `FAILED:`. Keep the return-code branch for genuine
  process errors (OSError / timeout).

## Verification

- A `task_sync` failure (dirty worktree or unreachable remote) emits a warning
  and reports the unreconciled state, while still exiting 0.
- A chatlink task-creation run whose push fails logs an audit warning naming the
  reason, with the created task still committed locally.

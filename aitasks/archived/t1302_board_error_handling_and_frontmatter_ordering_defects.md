---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_board, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
implemented_with: claudecode/opus5
created_at: 2026-07-28 17:54
updated_at: 2026-07-29 09:54
completed_at: 2026-07-29 09:54
---

## Origin

Spawned from t1243_1 during Step 8b review. Both defects were surfaced while
building the board-movement characterization harness
(`tests/test_board_movement.py`); neither caused the symptom t1243_1 addressed,
and both are pre-existing and out of scope there.

## Upstream defects

- `.aitask-scripts/board/aitask_board.py:1046` — `refresh_git_status` catches
  `(subprocess.TimeoutExpired, FileNotFoundError)` while `refresh_lock_map`
  directly below it (`:1067`) also catches `OSError`. A `PermissionError` or
  other `OSError` raised by `subprocess.run` would therefore propagate out of a
  board refresh instead of degrading to "no git status", which is what the
  neighbouring handler does. Every board refresh and every task-move keypress
  goes through this call.
- `.aitask-scripts/lib/task_yaml.py:143-164` — `serialize_frontmatter`'s
  docstring states "board keys (`boardcol`, `boardidx`) always last", but the
  implementation inserts `original_key_order` first and then *re-assigns* the
  board keys. Re-assigning a key already present in a dict does **not** move it,
  so a task file whose frontmatter has `boardcol` in the middle keeps it in the
  middle. Verified:

      raw = "---\npriority: high\nboardcol: now\nstatus: Ready\nboardidx: 10\n---\nbody\n"
      serialize_frontmatter(*parse_frontmatter(raw))
      # -> priority, boardcol, status, boardidx   (board keys NOT last)

  Round-trip is byte-stable, so this is a contract/documentation discrepancy
  rather than data loss.

## Diagnostic context

t1243_1's fixture had to produce task files that survive a `Task.save()`
round-trip byte-identically, otherwise the byte differ would report a change
caused by re-serialization rather than by the move under test. That forced a
close reading of `serialize_frontmatter`, which is where the ordering claim was
found not to hold. The `refresh_git_status` gap was found while establishing
that a temp tree with no git repo degrades gracefully (it does, but only for the
two exception types listed).

## Suggested fix

- `refresh_git_status`: widen the `except` to include `OSError`, matching
  `refresh_lock_map`. Alternatively factor the shared "run a helper subprocess,
  degrade on failure" pattern out of both call sites.
- `serialize_frontmatter`: either honour the documented contract (delete the
  board keys from `ordered` before re-adding them, so they genuinely move last)
  or correct the docstring to "board keys are appended last **only when not
  already present**". Prefer honouring it — **t1243_8 splits `BOARD_KEYS` into
  `BOARD_LAYOUT_KEYS` / `BOARD_KEYS` and would inherit the wrong guarantee.**
  Any change here must keep the round-trip byte-stable; `tests/test_board_movement.py`
  will catch a regression, since its fixture relies on that stability.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-28T21:00:02Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-29T06:40:49Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-29T06:54:30Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:efb37283abe8c324

> **✅ gate:risk_evaluated** run=2026-07-29T06:54:30Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1302/risk_evaluated_2026-07-29T06:54:30Z-risk_evaluated-a1.log`

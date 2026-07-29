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
created_at: 2026-07-29 09:52
updated_at: 2026-07-29 22:01
completed_at: 2026-07-29 22:01
---

## Origin

Spawned from t1302 during Step 8b review. t1302 fixed the same class of defect
on the board's *refresh* path (`refresh_git_status`); these three sites are the
user-triggered dialog handlers and were explicitly out of scope there.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:4529` — `revert_task` catches only
  `(subprocess.TimeoutExpired, FileNotFoundError)`; a `PermissionError` or other
  `OSError` from the git-checkout subprocess propagates out of the dialog handler
  instead of surfacing as a "Revert failed" notification.
- `.aitask-scripts/board/aitask_board.py:4712` — `_do_lock` has the same
  too-narrow `except` in a `@work(thread=True)` worker; an `OSError` escapes the
  worker thread with the `LoadingOverlay` left un-popped.
- `.aitask-scripts/board/aitask_board.py:4779` — `_do_unlock` has the same
  too-narrow `except`, with the same un-popped `LoadingOverlay` consequence.

## Diagnostic context

t1302 fixed `refresh_git_status` (`:1044`), which caught
`(subprocess.TimeoutExpired, FileNotFoundError)` while its twin
`refresh_lock_map` (`:1067`) also caught `OSError`. A survey of the module's
`subprocess.run` call sites during that work found 30+ of them with differing
degrade semantics; most already include `OSError`, but the three listed above do
not. They were left alone because t1302's task scoped the fix to
`refresh_git_status`, and because these are user-triggered dialog actions rather
than refresh-path calls — the failure mode is different (a stuck modal /
unhandled exception in a Textual worker, not a crashed refresh).

The two worker cases are the more serious of the three: an exception escaping a
`@work(thread=True)` body skips the `call_from_thread(self.app.pop_screen)`
cleanup, so the `LoadingOverlay` stays on screen and the board appears hung.

## Suggested fix

Widen each `except` to include `OSError`, matching the majority of the module
(and `refresh_lock_map`). For `_do_lock` / `_do_unlock`, confirm the
`LoadingOverlay` pop happens on every failure path — consider a `try/finally`
so the overlay cleanup cannot be skipped by an unanticipated exception type
rather than relying on the tuple being exhaustive.

Note: t1302 deliberately rejected factoring a shared "run a helper subprocess,
degrade on failure" helper out of these call sites, on the grounds that the 30+
sites have genuinely different degrade semantics. If this task revisits that,
treat it as a separate, explicitly-scoped refactor.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-29T15:55:16Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-29T17:08:43Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-29T19:01:10Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:39a12eca1aeaebc3

> **✅ gate:risk_evaluated** run=2026-07-29T19:01:10Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1314/risk_evaluated_2026-07-29T19:01:10Z-risk_evaluated-a1.log`

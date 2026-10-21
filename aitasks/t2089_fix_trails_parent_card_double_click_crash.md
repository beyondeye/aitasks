---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, aitask_board, textual]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 09:06
updated_at: 2026-10-21 09:59
---

## Symptom

In the stand-alone `ait trails` TUI, double-clicking the **t1853** card (wave 2 of
the `art:trail-testmap-feature` trail) crashes the app:

```
File ".aitask-scripts/board/board_widgets.py", line 511, in on_click
    if children and self.task_data.filename not in self.app.expanded_tasks:
AttributeError: 'TrailsApp' object has no attribute 'expanded_tasks'
```

A single click only focuses the card and does not crash. The crash happens on a
double-click of **any live parent card whose children the task manager has
loaded**. It reproduced on t1853 (children t1853_4, t1853_7) and on t1855. A
double-click on a leaf card (e.g. t1939) does not crash.

## Root cause

Textual calls `on_<event>` for **every class in the MRO**. It stops early only
when a handler calls `event.prevent_default()`.

- `TrailTaskCard.on_click` (`board_trail_view.py:525`) and
  `TrailGhostCard.on_click` (`board_trail_view.py:583`) focus the card and, on
  `event.chain == 2`, call `self.app.action_view_details()`, which opens the
  `TrailDetailScreen`. Neither calls `event.prevent_default()`.
- Textual then runs the base `TaskCard.on_click` (`board_widgets.py:499`) as
  well. On a double-click it checks
  `self.app.check_action("toggle_children", None) is True`.
  `KanbanApp.check_action` returns False for `toggle_children` in the
  By-Trail view. `TrailsApp.check_action` (`trails_app.py:774`) does not handle
  that action, so it falls through to `return True`.
- For a parent card with children, the base handler then reads
  `self.app.expanded_tasks`. `TrailsApp` has no such attribute, so the app
  crashes after the detail screen has already been pushed.
- On leaf cards and inside `ait board`'s By-Trail view, the base handler still
  runs and calls `action_view_details()` a second time. Today that second call
  is harmless, but nothing is meant to make it.

The `CardHost` protocol docstring (`board_widgets.py:~110`) rests on the same
wrong belief: "`action_toggle_children` is reached only from
`TaskCard.on_click`, which the trail cards override". The test at
`tests/test_board_widgets.py:~130` pins a trail host that is missing only
`expanded_tasks`, on that same assumption.

## Fix

1. Call `event.prevent_default()` in both `TrailTaskCard.on_click` and
   `TrailGhostCard.on_click`, so the base `TaskCard.on_click` never runs for
   trail cards. Add a short comment on why: Textual dispatches handlers up the
   MRO.
2. Defence in depth: make `TrailsApp.check_action` return False for
   `toggle_children`. The App has no such binding and no children to expand,
   so the gate should not answer True.
3. Correct the `CardHost` docstring (and the comment in `TaskCard.on_click`
   if needed). Overriding a handler does not stop the base one from running;
   only `prevent_default()` does.
4. Regression tests, using the same harness style as `tests/test_trails_app.py`
   (`bf.load_trails_app()`, `run_test(size=(200, 48))`):
   - In `TrailsApp`, double-click a live parent card that has a child task. The
     app must not raise, and the screen stack must end with exactly one
     `TrailDetailScreen`.
   - Assert that the base `TaskCard.on_click` is not reached for a trail card,
     e.g. by patching `TaskCard.on_click` or `action_view_details` with a call
     counter, so the test also covers leaf cards and the board's By-Trail view.
   - A negative control: with the `prevent_default()` call removed, the parent
     card test must fail.

## Repro used during exploration

A Textual pilot against the real repo (read-only). It booted
`TrailsApp(..., initial_trail="art:trail-testmap-feature")`, found the
`TrailTaskCard` whose filename starts with `t1853_testmap`, and ran
`await pilot.click(card, times=2)`. The `AttributeError` above was raised.
With `times=1` there was no error.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T06:59:42Z status=pass attempt=1 type=human

---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, tmux, tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1446
created_at: 2026-08-07 12:12
updated_at: 2026-08-07 12:28
---

## Origin

Spawned from t1446 during Step 8b review. t1446 fixed one instance of
"an unverifiable tmux observation read as a negative verdict"; these are the
neighbours the audit turned up but deliberately left out of its scope.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:1410-1425` — `get_pane_option` returns
  `""` on `rc != 0`, and `compute_shadow_staleness` (`:538-550`) reads that empty
  string as "shadow has not analyzed anything yet: nothing to warn about"
  (`:538-540`). A tmux failure therefore suppresses a staleness warning. Note
  `compute_shadow_staleness` is already carefully tri-state for the *exception*
  path (it maps an exception to `(None, None)` = "preserve prior state") — it is
  only the failed-read-as-empty-string path that falls through to the positive
  verdict. Same class as t1446, different function.
- `.aitask-scripts/aitask_minimonitor.sh:37` and
  `.aitask-scripts/lib/agent_launch_utils.py:1567` — the single-instance guards
  test `pane_current_command` for `minimonitor` / `monitor_app`, but a live
  minimonitor pane reports `python`, so neither guard can ever fire. Confirmed
  live during t1446's verification fixture: `%423 4041322 python`. Harmless
  today (a second companion in one window is unusual) but dead code pretending
  to be a guard.
- `.aitask-scripts/lib/agent_launch_utils.py:1465-1603` — `maybe_spawn_minimonitor`
  spawns the companion but never arms the `pane-died` cleanup hook, so board- and
  codebrowser-launched windows carry a companion with no hook.
  `.aitask-scripts/lib/tui_switcher.py:1387` arms it with a **bare**
  `set-hook -p … pane-died` (index 0) — exactly the overwrite hazard
  `attach_shadow_cleanup_hook` (`agent_launch_utils.py:1390-1445`) was written to
  avoid, so a later shadow spawn can claim the slot. (Carried over from t1446's
  own "Out of scope" section; not re-verified live.)

## Diagnostic context

t1446: every `ait minimonitor` companion pane quit voluntarily during a
machine-wide stall because `discover_window_panes` collapsed any `rc != 0` into
`[]` and `_check_auto_close` read `[]` as "no other panes remain". The fix made
the observation explicit — `discover_window_panes` now returns
`(observed, panes)`, where `observed` is `True` only when tmux answered *and*
every non-blank record parsed.

Auditing the callers for the same conflation turned up the sites above. The
`get_pane_option` one is a true sibling defect (a tmux failure produces a
positive "nothing to warn about"); the guard and hook items are separate
minimonitor-lifecycle defects noticed in the same sweep.

## Suggested fix

For the staleness read: give `get_pane_option` an explicit
`(ok, value)` return (the shape `find_shadow_pane_status` at
`monitor_core.py:398-417` already uses in this module) and have
`compute_shadow_staleness` treat `ok == False` the same way it treats the
exception path — preserve prior state rather than returning
"nothing to warn about".

For the guards: match on the pane's *command line* (which contains
`minimonitor_app.py` / `monitor_app.py`) rather than `pane_current_command`,
or drop the guards if they are not wanted.

For the hooks: route both call sites through the existing
`attach_shadow_cleanup_hook` slot-safe helper instead of a bare `set-hook -p`.

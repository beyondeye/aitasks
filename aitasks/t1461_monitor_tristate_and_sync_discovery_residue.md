---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, tmux, tui]
gates: [risk_evaluated]
anchor: 1446
created_at: 2026-08-07 17:11
updated_at: 2026-08-07 17:11
---

## Origin

Spawned from t1451 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_minimonitor.sh:36` (pre-t1451) — the guard's
  self-exclusion compared `#{pane_pid}` against `$$`. Those are different
  processes whenever the script is not the pane's direct child, so the self-skip
  never worked either. **Moot as written** (t1451's guard needs no
  self-exclusion, since only a booted app writes the marker), recorded because
  the same `$$`-vs-`pane_pid` confusion could recur elsewhere — worth a sweep of
  other `#{pane_pid}` comparisons in the tree.
- `.aitask-scripts/monitor/monitor_app.py:2926` — the `c`-hotkey concern picker
  passes `stale=bool(stale)` to `ConcernPickerModal`, collapsing
  `compute_shadow_staleness`'s tri-state so an *indeterminate* staleness renders
  as "not stale". Behaviour is unchanged by t1451 (`False` and `None` both
  coerce to `False`) and a one-shot modal has no prior state to preserve — but
  it is the same conflation class t1451 fixed, on a surface that could later
  want to distinguish "unknown" from "current". `monitor_app.py:1118` (the
  auto-offer toast) has the same shape.
- `.aitask-scripts/monitor/monitor_core.py:1779` — `discover_window_panes` is
  still a **sync** `tmux_run` (5 s default timeout) reached from the async
  `_refresh_data` via `_check_auto_close`, so a stalled tmux can freeze the
  minimonitor UI for up to 5 s per tick. **Already tracked** as t1446's
  `async_window_pane_discovery` risk-mitigation follow-up; re-confirmed still
  present during t1451. Listed here only for completeness — check whether that
  task exists and is still open before duplicating it, and drop this bullet if
  so.

## Diagnostic context

t1451 fixed three instances of "an unverifiable tmux observation read as a
positive verdict": `get_pane_option` returning `""` on `rc != 0`, two
single-instance guards matching `#{pane_current_command}` (which reports
`python` for a live monitor), and `maybe_spawn_minimonitor` never arming the
`pane-died` cleanup hook.

Auditing those call sites turned up the residue above. The first was found while
rewriting the guard (the old self-exclusion was dead code in a second,
independent way). The second was found while confirming that changing
`compute_shadow_staleness`'s failure verdict from `False` to `None` was a no-op
for the full monitor — it is, precisely because both coerce through `bool()`,
which is what makes the tri-state unavailable there. The third was re-verified
against the current source rather than taken from t1446's notes.

None of these was in t1451's scope: the first is moot, the second is
behaviour-neutral today, and the third has an existing owner.

## Suggested fix

For the `$$` sweep: grep for `#{pane_pid}` comparisons against a shell `$$` and
replace with a `#{pane_id}` vs `$TMUX_PANE` comparison, which is the identity
tmux actually guarantees to a process inside a pane.

For the tri-state collapse: decide whether `ConcernPickerModal` / the toast want
a third "unknown" presentation. If they do, thread the `None` through instead of
`bool()`-ing it; if they do not, make the coercion explicit
(`stale is True`) with a comment saying indeterminate is deliberately shown as
not-stale, so the collapse is a decision rather than an accident.

For the sync discovery: confirm t1446's `async_window_pane_discovery` follow-up
task exists and is open; if it does, remove that bullet from this task's scope.

---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, tmux]
gates: [risk_evaluated]
anchor: 1382
created_at: 2026-08-03 16:18
updated_at: 2026-08-03 16:18
boardidx: 16384
---

## Context

Surfaced while implementing **t1382** (renamed agent windows in the monitor
TUIs). Pre-existing; t1382 narrowed the exposure but did not close it.

`_find_sibling_pane_id` in `.aitask-scripts/monitor/minimonitor_app.py` backs
the minimonitor's `tab` (focus the agent) and `enter` (send Enter to the agent)
keys. It resolves the followed agent in two rungs:

1. The followed-pane snapshot, which excludes shadow and companion panes by
   construction (they never enter `_snapshots`).
2. If that returns `None`, a raw `tmux list-panes` on the own window, taking
   the **first pane that is not this minimonitor's own pane**.

Rung 2 has no shadow filter. Its own docstring names the hazard it is meant to
avoid — "so that a shadow or other helper pane sharing the window is never
mistaken for the agent (t986)" — but that guarantee comes only from rung 1. If
rung 1 misses and a shadow shares the window, `tab` moves focus to the shadow
and, worse, `enter` sends a keystroke into the **shadow's** agent CLI rather
than the followed agent's.

## What t1382 already changed

Rung 1 was switched from `_find_own_agent_snapshot` (AGENT-only) to
`_find_own_window_snapshot` (category-agnostic), so a window renamed off the
`agent-` prefix now resolves at rung 1 instead of falling through. That closed
the common path. Rung 2 is still reachable when no snapshot resolves at all —
e.g. `_own_window_index` is unset (tmux window-index detection lagging the
first refresh), or the snapshot set is empty on an early tick.

## Proposed fix

Filter rung 2 the way discovery does — read `@aitask_shadow_target` alongside
`pane_id` and skip any pane carrying a non-empty value:

```
list-panes -t <own_window_id> -F "#{pane_id}\t#{@aitask_shadow_target}"
```

then apply `is_shadow_target()` (`monitor/monitor_core.py`), which is already
the pure, unit-tested predicate for exactly this field. Consider also skipping
companion panes via the same `_is_companion_process` check the discovery path
uses, so a second minimonitor in the window cannot be selected either.

## Acceptance criteria

- [ ] Rung 2 of `_find_sibling_pane_id` skips panes carrying
      `@aitask_shadow_target`
- [ ] A test drives rung 2 directly (force rung 1 to return `None`) with a
      window containing `[minimonitor, shadow, agent]` and asserts the **agent**
      pane id is returned — with a negative control proving the test fails
      against the unfiltered fallback
- [ ] Decide explicitly whether companion panes are also filtered at rung 2,
      and record the decision either way
- [ ] The docstring's t986 guarantee is true of both rungs, not just rung 1

## Reference

- `.aitask-scripts/monitor/minimonitor_app.py` — `_find_sibling_pane_id`,
  `_find_own_window_snapshot`
- `.aitask-scripts/monitor/monitor_core.py` — `is_shadow_target`,
  `SHADOW_TARGET_OPTION`, `_parse_list_panes`
- `aidocs/framework/shadow_agent.md` — the marker is the authoritative shadow
  classifier
- Archived plan for t1382 (`Upstream defects identified`)

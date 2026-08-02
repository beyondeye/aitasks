---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, minimonitor]
gates: [risk_evaluated]
anchor: 1282
created_at: 2026-07-28 23:52
updated_at: 2026-07-28 23:52
boardidx: 530
---

## Origin

Spawned from t1282 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:1477 — action_cycle_compare_mode`
  (`d`) resolves its target only through `self._focused_pane_id`, so the agent
  this minimonitor *follows* — pinned in the non-selectable `#mini-own-agent`
  panel and excluded from the card list — cannot have its idle-detection
  compare mode changed from its own minimonitor. Same reachability gap as
  t1282, different key.

## Diagnostic context

t1282 fixed the identical gap for `i` (Task Info). The root shape: the
followed agent is rendered by `_maybe_build_own_agent_panel` as plain,
non-focusable `Static`s and excluded from `_rebuild_pane_list`, so **any**
action that resolves through focus (`_get_focused_pane_id()` or the
`_focused_pane_id` attribute) can never target it. A "nothing focused"
fallback does not help: `_auto_select_own_window()` always focuses the first
list card when one exists, so such a fallback is dead code whenever another
agent is running.

Handlers scoped to the followed agent instead resolve via
`_find_own_agent_snapshot()` — `action_kill_own_agent` (`k`),
`action_pick_next_for_own` (`n`), and now `action_show_own_task_info` (`I`,
t1282).

`action_switch_to` (`s`) shares the focus-only resolution but was deliberately
left alone in t1282: switching to the followed agent's window lands where the
minimonitor already lives.

## Open question (decide before implementing)

Is the `d` gap actually a defect? Cycling idle-detection for the followed
agent may be intentionally out of reach, or simply never considered. Confirm
with the user before adding a key. If it is worth fixing, the established
pattern is a dedicated uppercase key (`D`) resolving via
`_find_own_agent_snapshot()` — mirroring `i` → `I` (t1282) and `e` → `E` —
rather than a fallback inside `action_cycle_compare_mode`.

## Suggested fix

Add `Binding("D", "cycle_own_compare_mode", ...)` next to the `d` row, an
`action_cycle_own_compare_mode()` resolving through `_find_own_agent_snapshot()`
(warning `"No followed agent in this window"` when unresolvable), a line in the
hard-coded `#mini-key-hints` panel, and the matching rows in
`website/content/docs/tuis/minimonitor/how-to.md`. Test alongside
`tests/test_minimonitor_own_task_info.py`, which pins the same contract for `I`.

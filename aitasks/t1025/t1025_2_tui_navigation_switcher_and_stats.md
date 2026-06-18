---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t1025_1]
issue_type: feature
status: Implementing
labels: [tui_switcher, stats_ui, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-18 00:01
updated_at: 2026-06-18 15:58
---

## Context

Second child of t1025 (depends on t1025_1). Wires the two-axis navigation model
into the TUI switcher and stats TUI, consuming the pure `group_sessions()` +
group list and the resolved `project_group` on `AitasksSession` from t1025_1.

Two axes: **left/right** cycles the derived ring (selected group's repos + any
active out-of-group repo); **`[` / `]`** cycles which project-group is selected.
See parent plan `aiplans/p1025_*.md`.

## Key Files to Modify

- `.aitask-scripts/lib/tui_switcher.py`:
  - `_cycle_session` (~:849-875): cycle the derived ring, not flat `_all_sessions`.
  - BINDINGS (~:435-436): add `[`/`]` → `action_prev_group`/`action_next_group`.
  - Add selected-group state; render group label in the session row.
- `.aitask-scripts/stats/stats_app.py`:
  - `_cycle_session` (~:487-513), `_build_session_items` (~:317-325): mirror.
  - BINDINGS (~:153-154): add `[`/`]` guarded by pane id.
  - Keep `ALL_SESSIONS_KEY` aggregate as a fixed ring member appended AFTER
    grouped+active entries, reachable by left/right, UNAFFECTED by `[`/`]`
    (layered by the ring builder, not the pure function).
- `.aitask-scripts/monitor/monitor_app.py` (~:885-899) and
  `.aitask-scripts/monitor/minimonitor_app.py` (~:761-777):
  `_switcher_selected_session` preselects a session possibly in another group —
  the switcher MUST set its selected group to follow that session's group on open.
- `aidocs/framework/tui_conventions.md` (~:156-189): document the two-axis model.

## Reference Files for Patterns

- Existing left/right cycling + multi-session state in both TUIs (cited lines).
- `TuiSwitcherMixin` consumers (board/codebrowser/brainstorm) for current TUI
  marking — verify no regression.

## Implementation Plan

1. Switcher: selected-group state var; default = attached session's resolved
   group (fallback "(ungrouped)"/first group). `[`/`]` re-derive ring + re-render.
2. left/right cycles the derived ring only.
3. Stats: mirror; layer the All-sessions aggregate on top of the pure ring.
4. Monitor/minimonitor: selected group follows the preselected session's group.
5. Update `tui_conventions.md` in this commit so the doc never lags the binding.

## Verification

- Headless ring-derivation tests through the real entry points (extend
  `tests/test_multi_session_primitives.sh` / `test_multi_session_monitor.sh`).
- `[`/`]` advances selected group; left/right stays within ring.
- Live-but-out-of-group repo appears in the ring while a different group selected.
- Cross-group preselection: switcher opens with selected group = preselected
  session's group (monitor/minimonitor path).
- Manual smoke: launch `ait board`/switcher with ≥2 groups + a live out-of-group
  session (covered live by t1025_5).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-18T12:58:05Z status=pass attempt=1 type=human

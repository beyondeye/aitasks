---
Task: t1025_2_tui_navigation_switcher_and_stats.md
Parent Task: aitasks/t1025_design_project_group_grouping_and_tui_navigation.md
Sibling Tasks: aitasks/t1025/t1025_1_*.md, aitasks/t1025/t1025_3_*.md, aitasks/t1025/t1025_4_*.md
Archived Sibling Plans: aiplans/archived/p1025/p1025_1_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: two-axis TUI navigation — switcher + stats (t1025_2)

Depends on t1025_1 (read its archived plan for the `group_sessions` signature and
`AitasksSession.project_group`). See parent plan `aiplans/p1025_*.md`.

## Steps

1. **TUI switcher** (`.aitask-scripts/lib/tui_switcher.py`):
   - Add a selected-group state var; default on mount = attached session's
     resolved `project_group` (fallback "(ungrouped)"/first group).
   - `_cycle_session` (`:849-875`): cycle the derived ring from
     `group_sessions(self._all_sessions, selected_group)`, not flat `_all_sessions`.
   - BINDINGS (`:435-436`): add `[`/`]` → `action_prev_group`/`action_next_group`
     that advance the selected group, re-derive the ring, and re-render.
   - Render the group label in the session row.
2. **stats TUI** (`.aitask-scripts/stats/stats_app.py`):
   - `_cycle_session` (`:487-513`) + `_build_session_items` (`:317-325`): mirror.
   - BINDINGS (`:153-154`): add `[`/`]`, guarded by pane id like the arrows.
   - Keep `ALL_SESSIONS_KEY` as a fixed ring member appended AFTER grouped+active
     entries — reachable by left/right, UNAFFECTED by `[`/`]`. Layer it in the
     ring builder, not the pure `group_sessions()`.
3. **Monitor/minimonitor** preselection — `_switcher_selected_session` overrides
   in `.aitask-scripts/monitor/monitor_app.py` (`:885-899`) and
   `.aitask-scripts/monitor/minimonitor_app.py` (`:761-777`) may name a session in
   another group. The switcher MUST set its selected group to follow that
   session's group on open, so the preselected repo is inside the ring.
4. **Conventions doc** — update `aidocs/framework/tui_conventions.md` (`:156-189`)
   with the two-axis model in the same commit.

## Verification

- Headless ring-derivation through the real entry points (extend
  `tests/test_multi_session_primitives.sh` / `test_multi_session_monitor.sh`).
- `[`/`]` advances the selected group; left/right stays within the ring.
- A live-but-out-of-group repo appears in the ring while a different group is
  selected.
- Cross-group preselection: switcher opens with selected group = preselected
  session's group (monitor + minimonitor paths).
- No regression for `TuiSwitcherMixin` consumers (board/codebrowser/brainstorm).

## Step 9
Standard child archival.

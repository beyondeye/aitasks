---
Task: t1033_consolidate_group_cycle_wiring.md
Worktree: /home/ddt/Work/aitasks
Branch: main
Base branch: main
plan_verified: []
---

# Plan: t1033 - Consolidate group-cycle wiring

## Summary

Factor the duplicated project-group cycle decision out of the TUI switcher and
stats TUI into a pure helper in `agent_launch_utils.py`. Keep each TUI's
widget refresh, notifications, aggregate fallback, and key-guard behavior at
the call site.

## Implementation

- Add a frozen `GroupCycleSelection` result type near the existing group
  helpers.
- Add `advance_group_selection(...)` to:
  - derive the shared group order with `group_sessions(...)`;
  - return `None` when there are fewer than two groups;
  - advance with `advance_selected_group(...)`;
  - derive target-group members with `group_members(...)`;
  - return the next group plus an optional session key to re-point to.
- Update `.aitask-scripts/lib/tui_switcher.py` so `_cycle_group` keeps its
  `_multi_mode` / `SkipAction` behavior, applies the helper result, and then
  runs `_refresh_after_cycle()`.
- Update `.aitask-scripts/stats/stats_app.py` so `_cycle_group` uses the helper
  with `fallback_session=ALL_SESSIONS_KEY`, preserving aggregate fallback and
  existing title/notification behavior.
- Extend `tests/test_project_groups.py` with pure helper coverage. Existing
  `tests/test_tui_group_nav.py` remains the behavioral regression suite for the
  two TUI call sites.

## Verification

- `python3 tests/test_project_groups.py`
- `python3 tests/test_tui_group_nav.py`

## Risk

### Code-health risk: low

- The change is localized to an existing non-UI helper module and two existing
  callers. The abstraction is pure and keeps UI-specific side effects outside
  the helper. -> mitigation: none

### Goal-achievement risk: low

- The task asks to consolidate only the residual group-cycle wiring duplication;
  the helper directly covers the duplicated decision while preserving different
  refresh behavior in each TUI. -> mitigation: none

## Final Implementation Notes

- **Actual work done:** Added `GroupCycleSelection` and
  `advance_group_selection(...)` to centralize the group-cycle state decision,
  then rewired the switcher and stats `_cycle_group` methods to use it.
- **Deviations from plan:** None.
- **Issues encountered:** `pytest` was not installed in the active environment,
  so verification used the direct unittest entrypoints advertised by the tests.
- **Key decisions:** Kept the abstraction pure and left UI-specific refresh,
  notifications, aggregate fallback, and `SkipAction` behavior in the callers.
- **Upstream defects identified:** None

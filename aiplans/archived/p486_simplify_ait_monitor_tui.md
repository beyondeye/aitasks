---
Task: t486_simplify_ait_monitor_tui.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Simplify ait monitor TUI (t486)

## Context
The monitor TUI had 3 panes: "NEEDS ATTENTION" (idle agents), "pane list" (all agents + other windows), and "content preview". The attention pane duplicated information already visible in the pane list (idle agents show yellow dots + "IDLE Ns" status + task info). Removing it simplifies the UI to 2 zones.

## File Modified
- `.aitask-scripts/monitor/monitor_app.py` (1087 -> 960 lines)

## Changes Made
1. Updated module docstring to reflect 2-zone model
2. Removed `Zone.ATTENTION` from enum and `ZONE_ORDER`
3. Removed `AttentionCard` widget class
4. Removed all attention-related CSS (6 blocks)
5. Removed attention section from `compose()`
6. Removed `self.attention_queue` from `__init__`
7. Removed `_update_attention_queue()` and `_rebuild_attention_section()` methods
8. Simplified `_refresh_data()`, `_restore_focus()`, `_switch_zone()`, `_focus_first_in_zone()`, `_update_zone_indicators()`, `_nav_within_zone()`, `on_descendant_focus()`, `_get_focused_pane_id()`
9. Simplified session bar (removed idle count)

## Final Implementation Notes
- **Actual work done:** Removed the entire "NEEDS ATTENTION" attention zone from the monitor TUI, leaving only the pane list and content preview zones. All attention-related code was cleanly removed (widget, CSS, compose element, queue tracking, rebuild method, zone navigation references, focus handlers).
- **Deviations from plan:** None — straightforward removal as planned.
- **Issues encountered:** The file had grown from 854 to 1087 lines since the task was created (new TaskInfoCache, TaskDetailDialog, task info display features were added). Plan line numbers needed re-verification against the current state.
- **Key decisions:** Kept idle status display in the pane list (yellow dots + "IDLE Ns") — agents that need attention are still visible, just not in a separate pane. Removed idle count from session bar since the attention queue no longer exists.

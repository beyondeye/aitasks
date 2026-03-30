---
Task: t481_monitor_footer_tab_shortcut.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The monitor TUI footer shows bindings for Jump TUI (j), Quit (q), Switch (s), Refresh (r), and Zoom (z), but Tab (zone cycling) is not listed. Since Tab is the primary navigation mechanism (added in t477), it should be visible in the footer.

## Plan

**File:** `.aitask-scripts/monitor/monitor_app.py`

Add a "Tab: switch pane" hint (dimmed) to the session bar text in `_rebuild_session_bar()`.

## Verification

- Run `ait monitor` and confirm "Tab: switch pane" appears in the session bar
- Press Tab to verify zone cycling still works

## Final Implementation Notes
- **Actual work done:** Added `[dim]Tab: switch pane[/]` suffix to the session bar string in `_rebuild_session_bar()` (line 482)
- **Deviations from plan:** Original plan used Textual `Binding` + footer approach, but Tab bindings don't render in the Textual Footer widget. Switched to appending the hint directly to the session bar text per user feedback.
- **Issues encountered:** Textual's Footer widget does not display Tab key bindings even when added to BINDINGS with a no-op action method.
- **Key decisions:** Used `[dim]` Rich markup to visually differentiate the hint from the session info.

---
Task: t516_live_preview_task_name_in_footer.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

In `ait monitor`, the preview panel header was at the top showing only the tmux window name. Users' eyes are typically at the bottom watching the agent output, and the task name was not shown.

## Plan

1. Move `#content-header` Static widget from top to bottom of the `#content-section` Container in `compose()`
2. Add `dock: bottom` CSS to `#content-header`, change `border-top` to `border-bottom` on `#content-section`
3. Resolve task name via existing `TaskInfoCache` in `_update_content_preview()` and append to footer label
4. Update comment from "header" to "footer"

## Post-Review Changes

### Change Request 1 (2026-04-10 10:35)
- **Requested by user:** Footer style should have more emphasis when the live preview panel is selected (brighter/bold)
- **Changes made:** Added zone-aware styling — when preview zone is active, footer uses `[bold white]` for "Content Preview" and `[bold]` for task name; when inactive, uses default muted/dim italic styling
- **Files affected:** `.aitask-scripts/monitor/monitor_app.py`

## Final Implementation Notes
- **Actual work done:** Moved preview panel label from top to bottom, added task name resolution using existing `TaskInfoCache`, added zone-aware footer emphasis
- **Deviations from plan:** Added conditional bold/bright styling for active zone (user feedback)
- **Issues encountered:** None
- **Key decisions:** Reused existing `_task_cache.get_task_id()` / `get_task_info()` pattern already used in pane list for consistency

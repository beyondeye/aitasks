---
Task: t488_crash_in_ait_monitor_live_preview.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `ait monitor` TUI crashes during live preview mode. The root cause is a race condition: the 0.3s preview refresh timer (`_fast_preview_refresh`) calls `_update_content_preview()` which uses unprotected `query_one()` calls. When a full data refresh triggers `_rebuild_pane_list()` (which removes and remounts widgets), the timer can fire mid-rebuild, causing Textual's `NoMatches` exception to propagate unhandled.

## Plan

### 1. Wrap `_update_content_preview()` query_one calls in try/except

**File:** `.aitask-scripts/monitor/monitor_app.py` (lines 664-686)

### 2. Wrap `_update_zone_indicators()` query_one calls in try/except

**File:** `.aitask-scripts/monitor/monitor_app.py` (lines 719-728)

Both follow the existing error handling pattern at lines 594-598 and 714-717.

## Final Implementation Notes
- **Actual work done:** Added try/except guards to `_update_content_preview()` and `_update_zone_indicators()` to handle widget lookup failures during rebuild race conditions
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Kept the existing pattern of catching broad `Exception` and returning silently, consistent with the rest of the codebase

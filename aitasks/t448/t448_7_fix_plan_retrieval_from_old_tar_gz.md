---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, task-archive]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-24 13:35
updated_at: 2026-03-24 21:09
---

## Context

This is child task 7 of t448 (Completed Tasks History View in Codebrowser). During t448_4 testing, it was discovered that toggling to plan view (pressing `v`) in the history detail pane shows "No plan file found" for tasks whose files are archived inside `old.tar.gz` (or numbered `_bN/oldN.tar.gz`) archives.

The issue is in the data retrieval layer, not the UI. Task content for these archived tasks loads correctly (the task description is shown), but the corresponding plan content does not.

## Key Files to Investigate
- `.aitask-scripts/codebrowser/history_data.py` — `load_plan_content()` function (the likely culprit)
- `.aitask-scripts/codebrowser/history_data.py` — `load_task_content()` function (works correctly — use as reference)
- `.aitask-scripts/lib/archive_iter.py` — archive iteration utilities (tar extraction helpers)

## Reference Files
- `aiplans/archived/p448/p448_1_consolidate_archive_iter_and_history_data_layer.md` — the original plan for the data layer (t448_1), contains full API documentation
- `.aitask-scripts/codebrowser/history_detail.py` — `action_toggle_view()` and `_get_body_content()` show how plan content is retrieved and displayed

## Suspected Root Cause

`load_plan_content()` in `history_data.py` likely only checks loose plan files in `aiplans/archived/` but does not search inside tar.gz archives. The plan archives may have a different directory structure or naming convention than task archives, or `load_plan_content()` may not use the archive iteration utilities at all.

Compare with `load_task_content()` which successfully loads task content from tar archives — the same pattern should apply to plans.

## Implementation

1. Read `load_plan_content()` and `load_task_content()` in `history_data.py`
2. Identify why plan content fails for tar-archived tasks
3. Fix `load_plan_content()` to search tar archives using the same pattern as `load_task_content()`
4. Verify the plan archive directory structure matches expectations (plans use `p` prefix, tasks use `t` prefix)

## Verification

1. Launch `ait codebrowser` → press `h`
2. Select a task that is known to be archived in old.tar.gz (typically older tasks with low IDs)
3. Press `v` to toggle to plan view — should now show plan content instead of "No plan file found"
4. Toggle back with `v` — task content still displays correctly

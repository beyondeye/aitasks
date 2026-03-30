---
Task: t485_more_info_for_codeagent_windows.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The monitor TUI currently shows agent windows with just their tmux window name (e.g., `agent-pick-42`). Users must mentally map these names to actual tasks or switch to the board TUI to see task details. This feature adds task context information directly in the monitor: extracting task IDs from window names, showing task titles inline, and providing a simple read-only dialog for viewing full task content and plan.

## Implementation Plan

**File to modify:** `.aitask-scripts/monitor/monitor_app.py`

### 1. Add imports and sys.path setup

- Add `import re` and `from dataclasses import dataclass` at top
- Add `sys.path.insert(0, str(_SCRIPT_DIR / "board"))` after existing sys.path lines
- Add `from task_yaml import parse_frontmatter` and `Markdown` widget import

### 2. TaskInfo dataclass and TaskInfoCache class

- `_TASK_ID_RE` regex to extract task IDs from window names like `agent-pick-42`, `agent-qa-16_2`
- `TaskInfo` dataclass holding task metadata, body, and plan content
- `TaskInfoCache` with pure-Python file resolution (no subprocess), caching results

### 3. TaskDetailDialog modal

- Simple read-only `ModalScreen` with metadata summary + `Markdown` widget
- `p` key toggles between task content and plan content
- `q`/`Esc` dismisses

### 4. MonitorApp changes

- Add `project_root` parameter and `_task_cache` to `__init__`
- Add `i` keybinding for `action_show_task_info`
- Enhance `_rebuild_pane_list()` and `_rebuild_attention_section()` to show task titles
- Add `action_show_task_info()` method
- Pass `project_root` in `main()`

### 5. Verification

1. Run `ait monitor` with active agent windows
2. Verify task titles appear on agent cards
3. Press `i` to open TaskDetailDialog
4. Press `p` to toggle plan view
5. Press `q`/`Esc` to close

## Final Implementation Notes

- **Actual work done:** All planned changes implemented in a single file (`monitor_app.py`). Added `TaskInfo` dataclass, `TaskInfoCache` with pure-Python file glob resolution, `TaskDetailDialog` modal with task/plan toggle, inline task titles on agent cards, and `i` keybinding for task info dialog.
- **Deviations from plan:** Minor label change — the `p` shortcut was renamed from "Toggle Plan" to "Plan/Task" and footer hint changed to "p: switch plan/task" per user feedback.
- **Issues encountered:** None — implementation was straightforward. All imports resolved correctly, syntax check passed, and task ID extraction regex works for all expected window name formats.
- **Key decisions:** Used pure Python file glob for task resolution instead of subprocess calls to `aitask_query_files.sh`, avoiding shell overhead on every 3-second refresh cycle. Cache invalidation is only done on explicit `i` key press to get fresh content.

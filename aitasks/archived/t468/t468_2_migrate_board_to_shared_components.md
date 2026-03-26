---
priority: medium
effort: medium
depends: [t468_1]
issue_type: refactor
status: Done
labels: [codebrowser, ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-26 09:54
updated_at: 2026-03-26 23:42
completed_at: 2026-03-26 23:42
---

## Context

Child task 1 (t468_1) created shared components in `.aitask-scripts/lib/`: `AgentCommandScreen` (generalized modal widget) and `agent_launch_utils` (shared `find_terminal()` and `resolve_dry_run_command()`). This task migrates the board TUI to use these shared components, validating them before the codebrowser adopts them.

## Key Files to Modify

1. **`.aitask-scripts/board/aitask_board.py`** — Main board TUI application (~3400+ lines)

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_command_screen.py` — Shared `AgentCommandScreen` widget (created in t468_1)
- `.aitask-scripts/lib/agent_launch_utils.py` — Shared `find_terminal()` and `resolve_dry_run_command()` (created in t468_1)
- `.aitask-scripts/board/aitask_board.py:1616-1679` — `PickCommandScreen` to delete
- `.aitask-scripts/board/aitask_board.py:2727-2752` — Pick command CSS to delete from app CSS
- `.aitask-scripts/board/aitask_board.py:3298-3307` — `_find_terminal()` method to delete
- `.aitask-scripts/board/aitask_board.py:3389-3404` — `_resolve_pick_command()` to delegate

## Implementation Plan

1. **Add imports** (near line 14-15, where `sys.path.insert` for `lib/` already exists):
   ```python
   from agent_command_screen import AgentCommandScreen
   from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command
   ```
   Note: `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))` already exists on line 14.

2. **Delete `PickCommandScreen` class** (lines 1616-1679):
   - Remove the entire class definition

3. **Delete pick command CSS** from the app's `CSS` string (lines 2727-2752):
   - Remove the `#pick_command_dialog`, `#pick_command_title`, `#pick_command_full`, `#pick_command_prompt`, `.pick-copy-row`, `.pick-copy-row Button` rules
   - The CSS is now in `AgentCommandScreen.DEFAULT_CSS` with renamed IDs (`agent_cmd_*`)

4. **Delete `_find_terminal()` method** (lines 3298-3307):
   - Remove the method entirely. The shared `find_terminal()` is imported as `_find_terminal`.
   - Note: The shared version includes modern terminals (alacritty, kitty, ghostty, foot) that the board's version was missing — this is an improvement.

5. **Update `_resolve_pick_command()`** (lines 3389-3404):
   - Replace the body with: `return resolve_dry_run_command(Path("."), "pick", task_num.lstrip("t"))`
   - Keep the method as a thin wrapper for the fallback behavior in callers

6. **Update `action_pick_task()`** (line 3278):
   - Change `PickCommandScreen(num, full_cmd, prompt_str)` to `AgentCommandScreen(f"Pick Task t{num}", full_cmd, prompt_str)`

7. **Update `action_view_details()` pick branch** (line 3224-3225):
   - Same change: `PickCommandScreen(num, full_cmd, prompt_str)` → `AgentCommandScreen(f"Pick Task t{num}", full_cmd, prompt_str)`

8. **Update all `self._find_terminal()` calls** to `_find_terminal()`:
   - Line 3380: `_run_interactive_sync` method
   - Line 3414: `run_aitask_pick` method
   - Line 3428: `action_create_task` method

## Verification Steps

1. Run `ait board` — verify it starts without import errors
2. Press `p` on a task — verify the modal dialog appears with "Pick Task tN" title
3. Verify copy command (c), copy prompt (p), run in terminal (r), and cancel (escape) all work
4. Open task detail (enter) → press `p` — verify same modal appears
5. Verify `_find_terminal` fallback works correctly (if no terminal found, TUI suspends)

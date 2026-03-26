---
Task: t468_2_migrate_board_to_shared_components.md
Parent Task: aitasks/t468_better_codeagent_launching.md
Sibling Tasks: aitasks/t468/t468_1_shared_agent_command_screen_and_utils.md, aitasks/t468/t468_3_add_launch_modal_to_codebrowser.md
Archived Sibling Plans: aiplans/archived/p468/p468_1_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Migrate Board to Shared Components

## Overview

Replace the board TUI's `PickCommandScreen`, `_find_terminal()`, and `_resolve_pick_command()` with imports from the shared modules created in t468_1.

## Single file to modify

`.aitask-scripts/board/aitask_board.py`

## Step 1: Add imports (near line 15)

The `sys.path.insert` for `lib/` already exists at line 14. Add:

```python
from agent_command_screen import AgentCommandScreen
from agent_launch_utils import find_terminal as _find_terminal, resolve_dry_run_command
```

Import `find_terminal` as `_find_terminal` to match the existing `self._find_terminal()` call pattern (minimizes changes at call sites to just dropping `self.`).

## Step 2: Delete `PickCommandScreen` class (lines 1616-1679)

Remove the entire class. It is fully replaced by `AgentCommandScreen`.

## Step 3: Delete pick command CSS from app CSS string (lines 2727-2752)

Remove these CSS rules from the `KanbanApp.CSS` string:
- `#pick_command_dialog { ... }`
- `#pick_command_title { ... }`
- `#pick_command_full, #pick_command_prompt { ... }`
- `.pick-copy-row { ... }`
- `.pick-copy-row Button { ... }`

These are now in `AgentCommandScreen.DEFAULT_CSS` with renamed IDs.

## Step 4: Delete `_find_terminal()` method (lines 3298-3307)

Remove the method. Replaced by the imported `_find_terminal()` function (which has a superset terminal list including alacritty, kitty, ghostty, foot).

## Step 5: Update `_resolve_pick_command()` (lines 3389-3404)

Replace the method body to delegate to shared utility:

```python
def _resolve_pick_command(self, task_num: str):
    """Resolve the full pick command via --dry-run, return command string or None."""
    num = task_num.lstrip("t")
    return resolve_dry_run_command(Path("."), "pick", num)
```

Keep the method as a thin wrapper — callers use it for the fallback pattern (if None, launch directly).

## Step 6: Update `PickCommandScreen` references

### In `action_pick_task()` (around line 3278):
```python
# Before:
PickCommandScreen(num, full_cmd, prompt_str),
# After:
AgentCommandScreen(f"Pick Task t{num}", full_cmd, prompt_str),
```

### In `action_view_details()` pick branch (around line 3224-3225):
```python
# Before:
PickCommandScreen(num, full_cmd, prompt_str),
# After:
AgentCommandScreen(f"Pick Task t{num}", full_cmd, prompt_str),
```

## Step 7: Update `self._find_terminal()` calls

Three call sites, all change from `self._find_terminal()` to `_find_terminal()`:

1. `_run_interactive_sync()` (line 3380)
2. `run_aitask_pick()` (line 3414)
3. `action_create_task()` (line 3428)

## Verification

1. Run `ait board` — verify starts without errors
2. Press `p` on a task — verify modal dialog appears with "Pick Task tN" title
3. Test `c` (copy command), `p` (copy prompt), `r` (run), `escape` (cancel)
4. Open task detail → press `p` — verify same modal appears
5. Verify sync, create task, and pick all use terminal detection correctly

## Final Implementation Notes

- **Actual work done:** Migrated board TUI from `PickCommandScreen` to shared `AgentCommandScreen`, replaced `_find_terminal()` with shared `find_terminal()`, delegated `_resolve_pick_command()` to `resolve_dry_run_command()`. Also added `TmuxLaunchConfig` callback handling and removed unused `shutil` import.
- **Deviations from plan:**
  - Plan suggested importing `find_terminal as _find_terminal` to minimize call-site changes. Instead imported as `find_terminal` directly and changed all call sites (cleaner, no aliasing).
  - Added `TmuxLaunchConfig` and `launch_in_tmux` imports — needed for the AgentCommandScreen's tmux dismiss result callback pattern.
  - Fixed bugs in `agent_command_screen.py` (not in original plan scope):
    - `Select.BLANK` is `False` in Textual 8.1.1, causing `InvalidSelectValueError` on mount. Fixed session select to default to `_NEW_SESSION_SENTINEL` when no sessions, window select to use `allow_blank=True` without explicit value, and `.clear()` instead of `value = Select.BLANK`.
    - Input widget auto-focus on dialog open blocked keyboard shortcuts. Added `set_focus(None)` in `on_mount`.
    - Esc key now first unfocuses Input widgets before dismissing the dialog.
- **Issues encountered:** `resolve_dry_run_command` expects `Path` for project root, not a string path to the script — initial call passed `str(CODEAGENT_SCRIPT)` instead of `Path(".")`.
- **Notes for sibling tasks:** The `AgentCommandScreen` has Textual 8.1.1 compatibility fixes. The `Select.BLANK`/`Select.NULL` mismatch in Textual 8.1.1 should be kept in mind — never use `Select.BLANK` for initialization or assignment; use `allow_blank=True` constructor arg and `.clear()` method instead.

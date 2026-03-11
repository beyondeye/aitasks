---
Task: t367_improved_task_pick_from_bard.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

When using `ait board` TUI with a terminal multiplexer (tmux, etc.), clicking "Pick" on a task opens a new OS terminal window that is disconnected from the multiplexer. Users need a way to copy the command and paste it into their existing multiplexer pane instead.

## Solution

Replace the direct terminal launch with a dialog that shows the resolved command, copy buttons, and a "Run in new terminal" fallback.

## File Modified

`.aitask-scripts/board/aitask_board.py`

## Implementation Steps

### 1. Added `PickCommandScreen` class (after `ResetTaskConfirmScreen`, line ~1549)

New `ModalScreen` subclass with:
- Constructor: `task_num`, `full_command`, `prompt_str`
- Layout: title, full command label + copy button, prompt label + copy button, bottom buttons (Run in Terminal / Cancel)
- Keyboard shortcuts: `c` (copy command), `p` (copy prompt), `r` (run in terminal), `escape` (cancel)
- Copy uses `self.app.copy_to_clipboard(text)` + `notify` toast
- Dismisses with `"run"` or `None`

### 2. Added CSS for `#pick_command_dialog` (in `KanbanBoard.CSS`)

- 70% width dialog matching `commit_dialog` pattern
- `.pick-copy-row` horizontal layout for command + copy button pairs

### 3. Added `_resolve_pick_command()` helper on `KanbanBoard`

Runs `aitask_codeagent.sh --dry-run invoke pick <num>`, parses `DRY_RUN: <cmd>` output, returns command string or `None`.

### 4. Modified `check_edit()` pick branch

Instead of calling `run_aitask_pick()` directly:
1. Resolve command via `_resolve_pick_command()`
2. If resolved: show `PickCommandScreen` dialog, on "run" result call `run_aitask_pick()`
3. If resolution fails: fall back to direct `run_aitask_pick()` (existing behavior)

## Post-Review Changes

### Change Request 1 (2026-03-11 14:40)
- **Requested by user:** Button labels should show keyboard shortcuts visibly with parenthesized letters; accept both uppercase and lowercase
- **Changes made:** Renamed buttons to `(C)opy`, `Copy (P)rompt`, `(R)un in new terminal`; added uppercase `C`, `P`, `R` binding variants
- **Files affected:** `.aitask-scripts/board/aitask_board.py`

### Change Request 2 (2026-03-11 14:45)
- **Requested by user:** Add `p` keyboard shortcut on main board screen to open pick dialog directly when a task is focused
- **Changes made:** Added `Binding("p", "pick_task", "Pick")` after `n` (New Task), added `action_pick_task()` method, added `check_action` case to conditionally show only when a card is focused
- **Files affected:** `.aitask-scripts/board/aitask_board.py`

### Change Request 3 (2026-03-11 14:48)
- **Requested by user:** Move `p` shortcut in bindings list to be right after `n` (New Task) in the context-aware section
- **Changes made:** Moved binding position in BINDINGS list
- **Files affected:** `.aitask-scripts/board/aitask_board.py`

## Final Implementation Notes
- **Actual work done:** Added PickCommandScreen dialog, CSS, _resolve_pick_command helper, modified check_edit flow, and added `p` main-screen shortcut with conditional visibility
- **Deviations from plan:** Added main-screen `p` shortcut (not in original plan, requested during review)
- **Issues encountered:** None
- **Key decisions:** Used Textual's built-in `copy_to_clipboard()` (OSC 52) which works through tmux with `set -g set-clipboard on`; both case variants for shortcuts since Textual bindings are case-sensitive

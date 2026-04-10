---
Task: t495_better_shortcuts_docs_in_switcher.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Better Shortcuts Docs in TUI Switcher (t495)

## Context

The TUI switcher dialog (`.aitask-scripts/lib/tui_switcher.py`) shows keyboard shortcuts using dim-colored letters embedded in TUI names (`[dim]b[/]oard`). This is not clear enough. Change to parenthesized convention `(b)oard` with color coding. Also add "n" shortcut for `ait create` in a new tmux window.

## Changes (single file: `.aitask-scripts/lib/tui_switcher.py`)

### 1. Update bottom hint text (lines 254-258)

Replace `[dim]b[/]oard` format with `[bold bright_cyan](b)[/]oard` format for all shortcuts. Add `(n)ew task` entry. Apply same color to `Enter` and `j/Esc` action hints.

### 2. Update inline list item hints (line 183)

Change `[dim]({shortcut})[/]` to `[bold bright_cyan]({shortcut})[/]` so inline hints on list items match the new convention.

### 3. Add "n" binding (line 241)

Add `Binding("n", "shortcut_create", "New Task", show=False)` to `BINDINGS`.

### 4. Add `action_shortcut_create` method (after `action_shortcut_explore`)

Launch `ait create` in a new tmux window named `create-task`. No dialog (always tmux since switcher only runs in tmux). Pattern matches existing `action_shortcut_explore` but simpler (no minimonitor, no incrementing window name).

## Verification

- Launch `ait board`, press `j` to open switcher, verify new hint format
- Press `n` to verify create-task window opens in tmux
- Verify inline `(b)`, `(c)`, `(s)`, `(g)` hints on list items use new color

## Final Implementation Notes
- **Actual work done:** All 4 planned changes implemented exactly as planned in `.aitask-scripts/lib/tui_switcher.py`
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Used `bold bright_cyan` for shortcut color to match the existing cyan theme (current TUI indicator uses `bold cyan`). Left `_TUI_SHORTCUTS` dict unchanged since brainstorm/explore don't benefit from inline hints (their window names don't match dict keys).

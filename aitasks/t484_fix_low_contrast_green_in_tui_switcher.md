---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-30 12:12
updated_at: 2026-03-30 12:17
---

## Problem

The TUI switcher dialog (`.aitask-scripts/lib/tui_switcher.py`) uses `"green"` (Textual's dark `#008000`) for running TUI text style and indicator dots. When a running TUI item is selected/highlighted in the ListView, the dark green text has very low contrast against the selection background, making it hard to read.

## Affected Code

- **`_TuiListItem.compose()`** (line ~144): `style = "green"` for running TUIs
- **`_TuiListItem.compose()`** (line ~143): `indicator = "[green]●[/]"` for the running dot
- **`_WindowListItem.compose()`** (line ~163): `"[green]●[/]"` for non-TUI window dots

The current TUI uses `"bold cyan"` which has good contrast — the issue is only with running (non-current) items.

## Fix

Change `"green"` to a lighter green variant (e.g., `"bright_green"`, `#80ff80`, or similar high-contrast light green) for:
1. The `style` variable in the `elif self.running` branch
2. The indicator dot color in the same branch
3. The indicator dot in `_WindowListItem.compose()`

## Affected TUIs

The switcher is shared across all 5 TUIs: board, codebrowser, brainstorm, settings, monitor.

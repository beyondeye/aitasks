---
Task: t484_fix_low_contrast_green_in_tui_switcher.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The TUI switcher dialog uses dark green (`"green"` = `#008000`) for running TUI text and indicator dots. When a row is highlighted/selected in the ListView, this dark green has very poor contrast against the selection background, making text hard to read. The user wants a very light green instead.

## Plan

### File: `.aitask-scripts/lib/tui_switcher.py`

**Change 1 — `_TuiListItem.compose()` (lines 142-144):**

Change the running TUI branch from:
```python
indicator = "[green]●[/]"
style = "green"
```
to:
```python
indicator = "[bright_green]●[/]"
style = "bright_green"
```

**Change 2 — `_WindowListItem.compose()` (line 163):**

Change from:
```python
yield Static(f" [green]●[/]  {self.window_name}")
```
to:
```python
yield Static(f" [bright_green]●[/]  {self.window_name}")
```

### Color choice

`bright_green` is a standard Rich/Textual named color that maps to `#00ff00` — significantly lighter than `green` (`#008000`). This provides good contrast against both dark and selection backgrounds while keeping the semantic "running = green" association.

## Verification

1. Run `ait board` (or any TUI with the switcher)
2. Press `j` to open the TUI switcher
3. Navigate to a running TUI item — verify the text is bright/light green
4. Verify the indicator dot is also bright green
5. Check that the current TUI still shows as bold cyan
6. Check that stopped TUIs still show as dim

## Final Implementation Notes
- **Actual work done:** Changed all 3 instances of `"green"` to `"bright_green"` in `tui_switcher.py` — exactly as planned.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Used `bright_green` (Rich/Textual named color = `#00ff00`) rather than a custom hex value, keeping the code consistent with the existing named color pattern (`bold cyan`, `dim`).

---
Task: t596_missing_monitor_shortcut_from_tui_switcher.md
Base branch: main
plan_verified: []
---

# Plan: Add `m` keyboard shortcut for Monitor TUI in TUI switcher

## Context

Task t596 reports that the TUI switcher dialog (opened via `j` from any aitasks TUI) exposes one-key shortcuts for most known TUIs — `b` board, `c` codebrowser, `s` settings, `g` git, `r` brainstorm, `x` explore, `n` new task — but is **missing a shortcut for the monitor TUI**. The monitor entry is present in the switcher list (so you can arrow-key to it and press Enter) but cannot be opened with a single keypress like the other TUIs.

The natural shortcut is `m` for monitor. `m` is currently unbound in `TuiSwitcherOverlay.BINDINGS`, so no conflict.

## Files to Modify

Only one file: `.aitask-scripts/lib/tui_switcher.py`

## Changes

### 1. Register the shortcut in `_TUI_SHORTCUTS` (around line 86)

Add `"monitor": "m"` so the per-item `(m)` hint appears next to the Monitor entry in the list, matching how `(b)`, `(c)`, `(s)`, `(g)` are rendered by `_TuiListItem.compose()`:

```python
_TUI_SHORTCUTS = {
    "board": "b",
    "monitor": "m",
    "codebrowser": "c",
    "settings": "s",
    "git": "g",
}
```

### 2. Add a key binding in `TuiSwitcherOverlay.BINDINGS` (around line 232)

Insert `Binding("m", "shortcut_monitor", "Monitor", show=False)` next to the other TUI shortcuts (e.g., right after the `b` board binding):

```python
BINDINGS = [
    Binding("escape", "dismiss_overlay", "Close", show=False),
    Binding("j", "dismiss_overlay", "Close", show=False),
    Binding("enter", "select_tui", "Switch", show=False),
    Binding("b", "shortcut_board", "Board", show=False),
    Binding("m", "shortcut_monitor", "Monitor", show=False),
    Binding("c", "shortcut_codebrowser", "Code Browser", show=False),
    Binding("s", "shortcut_settings", "Settings", show=False),
    Binding("r", "shortcut_brainstorm", "Brainstorm", show=False),
    Binding("x", "shortcut_explore", "Explore", show=False),
    Binding("g", "shortcut_git", "Git", show=False),
    Binding("n", "shortcut_create", "New Task", show=False),
]
```

### 3. Add `action_shortcut_monitor` method (next to the other `action_shortcut_*` methods, around line 369)

Mirror the pattern of `action_shortcut_board` / `action_shortcut_codebrowser` / `action_shortcut_settings`:

```python
def action_shortcut_monitor(self) -> None:
    self._shortcut_switch("monitor")
```

`_shortcut_switch` already handles the "already the current TUI" no-op guard and launches the window via `ait monitor` (the launch command registered in `KNOWN_TUIS`) when not running.

### 4. Add `(m)onitor` to the footer hint label (around line 256)

Current line:
```python
yield Label(
    "[bold bright_cyan](b)[/]oard  [bold bright_cyan](c)[/]ode  [bold bright_cyan](s)[/]ettings  b[bold bright_cyan](r)[/]ainstorm  [bold bright_cyan](g)[/]it  e[bold bright_cyan](x)[/]plore  [bold bright_cyan](n)[/]ew task\n"
    "[bold bright_cyan]Enter[/] switch  [bold bright_cyan]j/Esc[/] close",
    id="switcher_hint",
)
```

Insert `(m)onitor` right after `(b)oard` to keep core TUIs grouped at the start of the hint:
```
(b)oard  (m)onitor  (c)ode  (s)ettings  b(r)ainstorm  (g)it  e(x)plore  (n)ew task
```

## Verification

1. Launch any aitasks TUI that uses `TuiSwitcherMixin` (e.g., `ait board` inside tmux).
2. Press `j` to open the TUI switcher overlay.
3. Confirm the Monitor list entry now shows a `(m)` hint on the right.
4. Confirm the footer hint line reads `(b)oard  (m)onitor  (c)ode  (s)ettings  b(r)ainstorm  (g)it  e(x)plore  (n)ew task`.
5. Press `m`:
   - If the `monitor` window does not yet exist in the current tmux session, a new window named `monitor` is created running `ait monitor`.
   - If it already exists, tmux switches to it.
6. From inside the monitor TUI itself, press `j` then `m` — nothing should happen (Monitor is the current TUI so `_shortcut_switch` short-circuits; the list entry is already disabled/marked current, matching the existing behavior for board/codebrowser/etc.).
7. Press `j` then `Esc` to confirm the overlay still dismisses normally.

No automated tests cover the switcher bindings (the file has no associated `tests/test_*` script). Manual verification above is sufficient.

## Step 9 (Post-Implementation) reminder

After the user reviews the change in Step 8, archive the task using `./.aitask-scripts/aitask_archive.sh 596`, then `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Four edits to `.aitask-scripts/lib/tui_switcher.py`:
  1. Added `"monitor": "m"` entry to `_TUI_SHORTCUTS` (shows the `(m)` hint next to the Monitor list item).
  2. Added `Binding("m", "shortcut_monitor", "Monitor", show=False)` to `TuiSwitcherOverlay.BINDINGS`, placed between the `b` board and `c` codebrowser bindings.
  3. Added `action_shortcut_monitor()` method delegating to `self._shortcut_switch("monitor")`, placed between `action_shortcut_board` and `action_shortcut_codebrowser`.
  4. Updated the footer hint `Label` to include `(m)onitor` right after `(b)oard`, keeping core TUIs grouped at the start.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Kept the new entries in the same board → monitor → code → settings order across `_TUI_SHORTCUTS`, `BINDINGS`, `action_*` methods, and the footer hint so code and UI stay visually aligned for future edits.
- **Verification:** `python3 -c "import ast; ast.parse(...)"` parses cleanly. Manual TUI verification per the plan's Verification section is required — no automated tests exist for the switcher bindings.

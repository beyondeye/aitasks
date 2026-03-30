---
Task: t480_2_add_explore_shortcut_to_tui_switcher.md
Parent Task: aitasks/t480_improve_aitaskexplore_integration.md
Sibling Tasks: aitasks/t480/t480_1_add_explore_operation_to_codeagent.md
Archived Sibling Plans: (check aiplans/archived/p480/ when starting)
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Add explore shortcut (`x`) to TUI switcher

All changes are in a single file: `.aitask-scripts/lib/tui_switcher.py`

## Steps

### 1. Add `x` binding to `TuiSwitcherOverlay.BINDINGS`

After the brainstorm binding (line 206), add:
```python
Binding("x", "shortcut_explore", "Explore", show=False),
```

### 2. Update help text

In `compose()` (lines 219-222), update the hint label to include the explore shortcut:

Change:
```python
"[dim]b[/]oard  [dim]c[/]ode  [dim]s[/]ettings  b[dim]r[/]ainstorm\n"
"[dim]Enter[/] switch  [dim]j/Esc[/] close",
```
To:
```python
"[dim]b[/]oard  [dim]c[/]ode  [dim]s[/]ettings  b[dim]r[/]ainstorm  e[dim]x[/]plore\n"
"[dim]Enter[/] switch  [dim]j/Esc[/] close",
```

### 3. Add `action_shortcut_explore()` method

After `action_shortcut_brainstorm()` (line 324), add:

```python
def action_shortcut_explore(self) -> None:
    """Launch a new explore agent session (always new window)."""
    n = 1
    while f"agent-explore-{n}" in self._running_names:
        n += 1
    window_name = f"agent-explore-{n}"
    try:
        subprocess.Popen(
            ["tmux", "new-window", "-t", f"{self._session}:",
             "-n", window_name, "ait codeagent invoke explore"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError):
        self.app.notify("Failed to launch explore", severity="error")
        return
    self.dismiss(window_name)
```

Key design decisions:
- **Always new window:** Uses `tmux new-window` unconditionally (never `select-window`)
- **Unique naming:** `agent-explore-{N}` with incrementing N based on running windows
- **`agent-` prefix:** Ensures `_classify_window()` groups these under "Code Agents"
- **Not in `_TUI_SHORTCUTS`:** Explore is not a TUI, it's an agent launch action
- **Not in `KNOWN_TUIS`:** Same reason — it's not a persistent TUI window

## Verification

1. Open any TUI (e.g., `ait board`)
2. Press `j` to open switcher
3. Verify help text shows `explore` with `x` shortcut
4. Press `x` — new `agent-explore-1` window should appear
5. Open switcher again, press `x` — new `agent-explore-2` window should appear (not switch to first)
6. Both explore windows should appear under "Code Agents" group in the switcher

## Step 9 (Post-Implementation)

Archive task and push changes per shared workflow.

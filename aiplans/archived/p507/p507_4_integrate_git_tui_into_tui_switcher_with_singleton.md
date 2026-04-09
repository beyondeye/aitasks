---
Task: t507_4_integrate_git_tui_into_tui_switcher_with_singleton.md
Parent Task: aitasks/t507_lazygit_integration_in_ait_monitorcommon_switch_tui.md
Sibling Tasks: aitasks/t507/t507_1_*.md, aitasks/t507/t507_2_*.md, aitasks/t507/t507_3_*.md
Archived Sibling Plans: aiplans/archived/p507/p507_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t507_4 — Integrate Git TUI into TUI Switcher

## Steps

### 1. Add `_build_tui_list()` function

File: `.aitask-scripts/lib/tui_switcher.py`

Add after `KNOWN_TUIS` definition (after line 67):

```python
def _build_tui_list():
    """Build TUI list including dynamic git TUI entry from config."""
    tuis = list(KNOWN_TUIS)
    try:
        from agent_launch_utils import load_tmux_defaults
        defaults = load_tmux_defaults()
        git_tui = defaults.get("git_tui", "")
        if git_tui and git_tui != "none":
            tuis.append(("git", f"Git ({git_tui})", git_tui))
    except Exception:
        pass
    return tuis
```

### 2. Add `g` shortcut to `_TUI_SHORTCUTS`

Line 74-79, add:
```python
_TUI_SHORTCUTS = {
    "board": "b",
    "codebrowser": "c",
    "settings": "s",
    "brainstorm": "r",
    "git": "g",
}
```

### 3. Add keybinding to `TuiSwitcherOverlay.BINDINGS`

Line 200-208, add:
```python
Binding("g", "shortcut_git", "Git", show=False),
```

### 4. Add `action_shortcut_git()` method

Add to `TuiSwitcherOverlay` class, near other shortcut actions:

```python
def action_shortcut_git(self) -> None:
    self._shortcut_switch("git")
```

### 5. Update `on_mount()` to use `_build_tui_list()`

Line 240, change:
```python
for name, label, _cmd in KNOWN_TUIS:
```
To:
```python
for name, label, _cmd in _build_tui_list():
```

### 6. Update `_get_launch_command()` to use dynamic list

Find `_get_launch_command()` method. Change it to search `_build_tui_list()` instead of `KNOWN_TUIS`:

```python
def _get_launch_command(self, name: str) -> str:
    for tui_name, _, cmd in _build_tui_list():
        if tui_name == name:
            return cmd
    return ""
```

### 7. Update hint label in `compose()`

Line 222, update the hint string to include git shortcut:

```python
yield Label(
    "[dim]b[/]oard  [dim]c[/]ode  [dim]s[/]ettings  b[dim]r[/]ainstorm  [dim]g[/]it  e[dim]x[/]plore\n"
    "[dim]Enter[/] switch  [dim]j/Esc[/] close",
    id="switcher_hint",
)
```

### 8. Handle `_shortcut_switch` gracefully for unconfigured git

The existing `_shortcut_switch()` method calls `_get_launch_command()`. If git is not configured, the command will be empty string (since `_build_tui_list()` won't include it). The method should handle this — check if it already does, or add a guard:

```python
def _shortcut_switch(self, name: str) -> None:
    cmd = self._get_launch_command(name)
    if not cmd:
        return  # TUI not configured
    # ... rest of switch logic
```

## Post-Implementation

Proceed to Step 9 (Post-Implementation) for archival.

## Verification

1. Set `tmux.git_tui: lazygit` in project_config.yaml
2. Open `ait board` → press `j` → verify "Git (lazygit)" appears in TUI list
3. Select it → lazygit launches in window named "git"
4. Press `j` again → git window shows as running (filled circle)
5. Press `g` → switches directly to git window
6. Set `tmux.git_tui:` (empty) → press `j` → git entry should NOT appear
7. Press `g` with empty config → should be no-op

## Final Implementation Notes
- **Actual work done:** Implemented all 7 steps from the verified plan. Added `_build_tui_list()` function that dynamically includes the git TUI from config, added `g` shortcut key to shortcuts dict and BINDINGS, added `action_shortcut_git()` with guard for unconfigured git, updated `on_mount()` and `_get_launch_command()` to use the dynamic list, and added `[dim]g[/]it` to the hint label.
- **Deviations from original plan:** (1) Plan verification corrected `load_tmux_defaults()` call to require `Path.cwd()` argument (original plan omitted it). (2) Removed lazy import from `_build_tui_list()` since `load_tmux_defaults` and `Path` are already module-level imports. (3) Preserved brainstorm prefix handler and generic fallback in `_get_launch_command()` (original plan removed them). (4) Used inline guard in `action_shortcut_git()` instead of modifying `_shortcut_switch()`.
- **Issues encountered:** None — all file paths matched, code compiled and loaded cleanly.
- **Key decisions:** Used `any(name == "git" for name, _, _ in _build_tui_list())` guard in `action_shortcut_git()` to make `g` a clean no-op when git TUI is not configured, rather than modifying the shared `_shortcut_switch()` method.
- **Notes for sibling tasks:** This was the final child task (t507_4). All t507 siblings are complete. The git TUI integration is now functional end-to-end: t507_1 added config/detection, t507_2 added setup detection, t507_3 added settings TUI field, and this task connected it to the TUI switcher.

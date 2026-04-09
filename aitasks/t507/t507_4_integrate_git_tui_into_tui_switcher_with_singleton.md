---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_monitor]
created_at: 2026-04-09 12:52
updated_at: 2026-04-09 12:52
---

## Context

Task t507 adds lazygit (or similar git TUIs) as a pseudo-native TUI in the aitasks framework. This child task integrates the configured git TUI into the TUI switcher overlay so users can launch and switch to it like any other native TUI. Depends on t507_1 which adds the config field and detection utility.

**IMPORTANT: This task is independent of t507_2 (setup) and t507_3 (settings). It only depends on t507_1.**

## Key Files to Modify

- `.aitask-scripts/lib/tui_switcher.py` — TUI switcher module (~400 lines)

## Reference Files for Patterns

- `.aitask-scripts/lib/tui_switcher.py` lines 59-67: `KNOWN_TUIS` list — static registry of `(window_name, display_label, launch_command)` tuples
- `.aitask-scripts/lib/tui_switcher.py` lines 74-79: `_TUI_SHORTCUTS` dict — shortcut keys for specific TUIs
- `.aitask-scripts/lib/tui_switcher.py` lines 200-208: `TuiSwitcherOverlay.BINDINGS` — keybindings including shortcuts b, c, s, r, x
- `.aitask-scripts/lib/tui_switcher.py` lines 217-225: `compose()` method — builds the overlay UI with hint label showing shortcuts
- `.aitask-scripts/lib/tui_switcher.py` lines 227-248: `on_mount()` — iterates KNOWN_TUIS to build the list, queries running windows
- `.aitask-scripts/lib/tui_switcher.py` lines 286+: action methods like `action_shortcut_board()`, `action_shortcut_codebrowser()` etc. — all call `self._shortcut_switch("name")`
- `.aitask-scripts/lib/tui_switcher.py` `_switch_to()` method — handles `tmux select-window` for running windows, `tmux new-window` for new ones
- `.aitask-scripts/lib/tui_switcher.py` `_get_launch_command()` — looks up launch command by window name from KNOWN_TUIS
- `.aitask-scripts/lib/agent_launch_utils.py`: `load_tmux_defaults()` — returns tmux config dict including `git_tui` field (added by t507_1)

## Implementation Plan

1. **Add `_build_tui_list()` function** that returns a list of TUI tuples:
   - Start with static `KNOWN_TUIS`
   - Read `tmux.git_tui` from config via `load_tmux_defaults()` (imported from agent_launch_utils)
   - If git_tui is set and not "none"/empty, append `("git", "Git (<tool_name>)", "<tool_name>")` to the list
   - Example: if git_tui is "lazygit", append `("git", "Git (lazygit)", "lazygit")`
   - Cache the result at module level or compute per-overlay mount

2. **Modify `TuiSwitcherOverlay.on_mount()`** (line 240):
   - Change `for name, label, _cmd in KNOWN_TUIS:` to use `_build_tui_list()` instead
   - This makes the git entry appear dynamically based on config

3. **Update `_get_launch_command()`** to use `_build_tui_list()` for lookup instead of static KNOWN_TUIS

4. **Add shortcut key `g` for git**:
   - Add `"git": "g"` to `_TUI_SHORTCUTS` dict
   - Add `Binding("g", "shortcut_git", "Git", show=False)` to `TuiSwitcherOverlay.BINDINGS`
   - Add `action_shortcut_git()` method that calls `self._shortcut_switch("git")`

5. **Update hint label** in `compose()` (line 222):
   - Add `[dim]g[/]it` to the hint string
   - Only show it if git_tui is configured (read config at compose time)

6. **Handle "not configured" gracefully**:
   - If git_tui is null/empty/"none", do not append the git entry to the TUI list
   - The `g` shortcut should be a no-op if git is not configured (check in action_shortcut_git)

## Verification Steps

1. Configure `tmux.git_tui: lazygit` in project_config.yaml
2. Open any TUI (e.g., `ait board`) → press `j` → verify "Git (lazygit)" appears in TUI list
3. Select it → verify lazygit launches in a tmux window named "git"
4. Press `j` again → verify the git window shows as "running" with filled circle indicator
5. Select it again → verify it switches to the existing window (singleton behavior)
6. Press `g` shortcut → verify direct switch to git TUI
7. Set `tmux.git_tui: none` → press `j` → verify git entry does NOT appear
8. Press `g` → verify it does nothing when not configured

---
priority: medium
effort: low
depends: [t480_1]
issue_type: feature
status: Implementing
labels: [aitask_explore, tmux]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-30 12:25
updated_at: 2026-03-30 21:52
---

## Summary

Add the `x` keyboard shortcut to the TUI switcher overlay that launches a new code agent running `/aitask-explore`. Unlike normal TUI shortcuts, explore ALWAYS opens a new window (never switches to an existing one).

## Context

Parent task t480 improves the aitask-explore UX. Child 1 (t480_1) adds the `explore` operation to the code agent system (`ait codeagent invoke explore`). This child adds the TUI-side integration — the `x` keyboard shortcut in the switcher overlay.

Key design decision: explore is NOT a TUI (like board, settings, etc.) — it's a code agent session. Therefore it should NOT be added to `KNOWN_TUIS` or `_TUI_SHORTCUTS`. Instead, it gets a dedicated action method that always creates a new tmux window with a unique name using the `agent-` prefix (so `_classify_window()` groups it under "Code Agents").

## Key Files to Modify

1. **`.aitask-scripts/lib/tui_switcher.py`** — all changes are in this single file:
   - `TuiSwitcherOverlay.BINDINGS` (line 207): Add `Binding("x", "shortcut_explore", "Explore", show=False)`
   - Help text in `compose()` (lines 219-222): Add `e[dim]x[/]plore` to the hint line
   - After `action_shortcut_brainstorm()` (line 324): Add new `action_shortcut_explore()` method that:
     - Counts existing `agent-explore-*` windows in `self._running_names` to generate a unique name like `agent-explore-1`, `agent-explore-2`, etc.
     - Runs `tmux new-window -t {session}: -n {window_name} ait codeagent invoke explore` unconditionally (always new window, never `select-window`)
     - Dismisses the overlay
   - Do NOT modify `_TUI_SHORTCUTS` dict — explore is not a TUI
   - Do NOT modify `KNOWN_TUIS` list — explore is not a TUI

## Reference Files for Patterns

- `.aitask-scripts/lib/tui_switcher.py` — see existing shortcut methods (`action_shortcut_board`, `action_shortcut_codebrowser`, etc.) at lines 314-324 for the pattern, and `_switch_to()` at lines 326-344 for the tmux launch mechanism
- `.aitask-scripts/lib/agent_launch_utils.py` — `launch_in_tmux()` for reference on tmux window creation patterns (though the switcher uses direct `subprocess.Popen` calls)

## Implementation Plan

1. Add the `x` binding to `BINDINGS` list
2. Update the help text label to include the explore shortcut
3. Add `action_shortcut_explore()` method:
   ```python
   def action_shortcut_explore(self) -> None:
       """Launch a new explore agent session (always new window)."""
       # Find next available explore window number
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

## Verification Steps

1. Open any TUI (e.g., `ait board`)
2. Press `j` to open the TUI switcher
3. Press `x` — a new `agent-explore-1` window should appear running the code agent with `/aitask-explore`
4. Open switcher again, press `x` — a second `agent-explore-2` window should appear (never switches to the first one)
5. The help text at the bottom of the switcher should show the `x` shortcut

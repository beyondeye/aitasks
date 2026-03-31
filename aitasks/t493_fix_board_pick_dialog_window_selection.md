---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [ui]
created_at: 2026-03-31 08:36
updated_at: 2026-03-31 08:36
---

## Problem

Two bugs in the board TUI "pick" dialog (`AgentCommandScreen`) when configuring tmux window selection for launching a new code agent:

### Bug 1: Arrow keys don't work in window selection dropdown

In `agent_command_screen.py`, the `on_key` handler (line ~488) checks `isinstance(focused, (Input, Select))` to decide whether to let the widget handle keys. When the Textual `Select` dropdown overlay is open, the focused widget is `SelectOverlay` (not `Select`), so the check fails. This may cause arrow key events to not propagate correctly to the dropdown, forcing users to use mouse-only selection.

**Fix:** Import `SelectOverlay` from `textual.widgets._select` (or use a more general check) and include it in the isinstance check, or check if the focused widget is a descendant of the Select widget.

### Bug 2: Selecting an existing window silently fails to spawn agent

Window option values are stored as `f"{idx}:{name}"` (e.g., `"0:main"`) at line ~329 of `agent_command_screen.py`. When an existing window is selected:

1. `_build_tmux_config()` sets `window = win_select.value` → `"0:main"` (line ~588)
2. `launch_in_tmux()` constructs the tmux target as `f"{config.session}:{config.window}"` → `"session:0:main"` (line ~144 of `agent_launch_utils.py`)
3. This is **invalid tmux target syntax** — tmux expects `session:window` where window is either an index OR a name, not `index:name`
4. The `tmux split-window` command fails, but the error only goes to stderr (line ~153), invisible to the TUI user

**Fix:** Either:
- Store only the window index as the option value (e.g., `f"{idx}"`) and keep `f"{idx}: {name}"` for display only
- Or parse the value in `_build_tmux_config` to extract just the index before the colon

Also surface tmux command failures via `app.notify()` instead of only printing to stderr.

## Files

- `.aitask-scripts/lib/agent_command_screen.py` — Dialog with Select widgets and key handling
- `.aitask-scripts/lib/agent_launch_utils.py` — `launch_in_tmux()` function

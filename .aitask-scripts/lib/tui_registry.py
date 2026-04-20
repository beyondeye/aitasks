"""tui_registry - Single source of truth for aitask TUI window registration.

Used by:
  - monitor/tmux_monitor.py     (pane classification)
  - lib/agent_launch_utils.py   (minimonitor auto-spawn exclusion)
  - lib/tui_switcher.py         (TUI switcher modal)

Adding a new TUI only requires adding one entry here.
"""
from __future__ import annotations

# Each entry: (window_name, display_label, launch_command, in_switcher)
#   - window_name: exact tmux window name (the -n flag when the window is created)
#   - display_label / launch_command: only meaningful when in_switcher is True
#   - in_switcher=False still classifies the name as a TUI window but hides it
#     from the switcher modal (per-task windows and companion panes)
TUI_REGISTRY: list[tuple[str, str | None, str | None, bool]] = [
    ("board",       "Task Board",    "ait board",       True),
    ("monitor",     "tmux Monitor",  "ait monitor",     True),
    ("codebrowser", "Code Browser",  "ait codebrowser", True),
    ("settings",    "Settings",      "ait settings",    True),
    ("stats",       "Statistics",    "ait stats-tui",   True),
    ("diffviewer",  "Diff Viewer",   "ait diffviewer",  True),
    ("brainstorm",  None,            None,              False),
    ("minimonitor", None,            None,              False),
]

# Window-name prefix also classified as TUI (per-task brainstorm windows).
BRAINSTORM_PREFIX = "brainstorm-"

# Full classification set. "git" is always included because the git TUI is
# surfaced dynamically from the `tmux.git_tui` config key and should classify
# as a TUI whenever a window with that name is present.
TUI_NAMES: frozenset[str] = frozenset({name for name, *_ in TUI_REGISTRY} | {"git"})


def switcher_tuis() -> list[tuple[str, str, str]]:
    """Return (name, label, command) tuples for TUIs shown in the switcher modal."""
    return [(n, l, c) for n, l, c, in_sw in TUI_REGISTRY if in_sw and l and c]

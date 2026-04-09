---
Task: t507_1_git_tui_config_field_and_detection_utility.md
Parent Task: aitasks/t507_lazygit_integration_in_ait_monitorcommon_switch_tui.md
Sibling Tasks: aitasks/t507/t507_2_*.md, aitasks/t507/t507_3_*.md, aitasks/t507/t507_4_*.md
Archived Sibling Plans: aiplans/archived/p507/p507_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t507_1 — Git TUI Config Field and Detection Utility

## Steps

### 1. Add `detect_git_tuis()` to `agent_launch_utils.py`

File: `.aitask-scripts/lib/agent_launch_utils.py`

Add after existing imports (shutil is likely already imported, if not add it):

```python
import shutil

# Known git management TUIs in preference order
KNOWN_GIT_TUIS = ["lazygit", "gitui", "tig"]

def detect_git_tuis() -> list[str]:
    """Return list of installed git TUI tool names."""
    return [tool for tool in KNOWN_GIT_TUIS if shutil.which(tool)]
```

### 2. Extend `load_tmux_defaults()` in `agent_launch_utils.py`

In the `load_tmux_defaults()` function, add `git_tui` to the returned dict. The function reads from `project_config.yaml` `tmux` section. Add:

```python
result["git_tui"] = tmux_cfg.get("git_tui", "")
```

### 3. Add `"git"` to `DEFAULT_TUI_NAMES` in `tmux_monitor.py`

File: `.aitask-scripts/monitor/tmux_monitor.py` line 30

Change:
```python
DEFAULT_TUI_NAMES = {"board", "codebrowser", "settings", "brainstorm", "monitor", "minimonitor", "diffviewer"}
```
To:
```python
DEFAULT_TUI_NAMES = {"board", "codebrowser", "settings", "brainstorm", "monitor", "minimonitor", "diffviewer", "git"}
```

### 4. Add `"git"` to `_TUI_NAMES` in `tui_switcher.py`

File: `.aitask-scripts/lib/tui_switcher.py` line 71

Change:
```python
_TUI_NAMES = {name for name, _, _ in KNOWN_TUIS}
```
To:
```python
_TUI_NAMES = {name for name, _, _ in KNOWN_TUIS} | {"git"}
```

### 5. Add `tmux:` section to `seed/project_config.yaml`

Add at the end of the file, following the documentation comment style:

```yaml
# ──────────────────────────────────────────────────────────────────────
# tmux — Tmux integration settings.
#
# These settings control how aitasks integrates with tmux sessions.
# ──────────────────────────────────────────────────────────────────────

tmux:
  # ──────────────────────────────────────────────────────────────────
  # git_tui — External git management TUI for the TUI switcher.
  #
  # Integrates an external git TUI (like lazygit, gitui, or tig) as a
  # "pseudo-native" TUI in the aitasks TUI switcher (press 'j' / 'g').
  # Only one instance runs per tmux session (singleton behavior).
  #
  # Set to the tool name (e.g., "lazygit") or leave empty to disable.
  # Detected automatically during `ait setup`.
  #
  # Supported tools:
  #   - lazygit  (recommended, most popular)
  #   - gitui    (Rust-based, fast)
  #   - tig      (ncurses-based, lightweight)
  #
  # Example:
  #   git_tui: lazygit
  # ──────────────────────────────────────────────────────────────────
  git_tui:
```

### 6. Update active `project_config.yaml`

File: `aitasks/metadata/project_config.yaml`

Add `git_tui: lazygit` under the existing `tmux:` section. Add `"git"` to `tmux.monitor.tui_window_names`.

## Post-Implementation

Proceed to Step 9 (Post-Implementation) for archival.

## Verification

- `python3 -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); from agent_launch_utils import detect_git_tuis; print(detect_git_tuis())"` — should list installed tools
- `grep git_tui seed/project_config.yaml` — should show the new field
- `grep '"git"' .aitask-scripts/monitor/tmux_monitor.py` — should appear in DEFAULT_TUI_NAMES

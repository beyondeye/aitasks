---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 12:50
updated_at: 2026-04-09 15:37
---

## Context

The aitasks framework has a TUI switcher system (press `j` in any TUI) that allows switching between native TUIs in tmux. Task t507 adds lazygit (or similar git management TUIs) as a "pseudo-native" TUI. This first child task establishes the configuration infrastructure and detection utility needed by all subsequent tasks.

## Key Files to Modify

- `seed/project_config.yaml` — Add `tmux:` section with `git_tui:` field and documentation comments. The seed currently has no tmux section at all. Follow the documentation comment pattern of other fields (verify_build, test_command, etc.).
- `aitasks/metadata/project_config.yaml` — Add `git_tui: lazygit` under `tmux:` section. Add `"git"` to `tmux.monitor.tui_window_names` list.
- `.aitask-scripts/lib/agent_launch_utils.py` — Add `detect_git_tuis() -> list[str]` function using `shutil.which()` to check for `lazygit`, `gitui`, `tig`. Extend `load_tmux_defaults()` to include `git_tui` from the config dict.
- `.aitask-scripts/monitor/tmux_monitor.py` — Add `"git"` to `DEFAULT_TUI_NAMES` set (currently at line 30: `{"board", "codebrowser", "settings", "brainstorm", "monitor", "minimonitor", "diffviewer"}`).
- `.aitask-scripts/lib/tui_switcher.py` — Add `"git"` to `_TUI_NAMES` set (line 71). Currently `_TUI_NAMES = {name for name, _, _ in KNOWN_TUIS}` — needs explicit addition since KNOWN_TUIS won't include git statically (that's done dynamically in t507_4).

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_launch_utils.py` — `load_tmux_defaults()` function shows how tmux config is loaded from project_config.yaml
- `.aitask-scripts/monitor/tmux_monitor.py` — `load_monitor_config()` shows config loading pattern
- `seed/project_config.yaml` — Documentation comment style for new config fields

## Implementation Plan

1. Add `detect_git_tuis()` function to `agent_launch_utils.py` that returns list of installed git TUI tool names
2. Extend `load_tmux_defaults()` to return `git_tui` value from config
3. Add `"git"` to `DEFAULT_TUI_NAMES` in `tmux_monitor.py`
4. Add `"git"` explicitly to `_TUI_NAMES` in `tui_switcher.py`
5. Add `tmux:` section with `git_tui:` field and documentation to `seed/project_config.yaml`
6. Add `git_tui: lazygit` and `"git"` to tui_window_names in active `project_config.yaml`

## Verification Steps

- `python3 -c "from agent_launch_utils import detect_git_tuis; print(detect_git_tuis())"` should return list of installed tools
- `grep git_tui seed/project_config.yaml` should show the new field
- `grep '"git"' .aitask-scripts/monitor/tmux_monitor.py` should show it in DEFAULT_TUI_NAMES

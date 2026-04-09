---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 12:51
updated_at: 2026-04-09 22:47
---

## Context

Task t507 adds lazygit (or similar git TUIs) as a pseudo-native TUI in the aitasks framework. This child task adds a git_tui configuration option to the Settings TUI Tmux tab and fixes a pre-existing data-loss bug in the tmux settings save logic. Depends on t507_1 which adds the config field and detection utility.

**IMPORTANT: This task is independent of t507_2 (setup) and t507_4 (switcher). It only depends on t507_1.**

## Key Files to Modify

- `.aitask-scripts/settings/settings_app.py` — Main settings TUI app (~3327 lines)

## Reference Files for Patterns

- `.aitask-scripts/settings/settings_app.py` line 370: `TMUX_CONFIG_SCHEMA` dict — defines the tmux settings fields. Currently has `default_session` (string), `default_split` (enum), `prefer_tmux` (bool).
- `.aitask-scripts/settings/settings_app.py` lines 2739-2744: `save_tmux_settings()` — THE BUG IS HERE. Currently does `data["tmux"] = tmux_data` which overwrites the entire tmux dict, wiping the `tmux.monitor` sub-dict (which contains `refresh_seconds`, `idle_threshold_seconds`, `capture_lines`, `agent_window_prefixes`, `tui_window_names`).
- `.aitask-scripts/settings/settings_app.py` `_populate_tmux_tab()` method (around line 2646): renders tmux settings from TMUX_CONFIG_SCHEMA
- `.aitask-scripts/lib/agent_launch_utils.py`: `detect_git_tuis()` function (added by t507_1) returns list of installed git TUI names

## Implementation Plan

### Part 1: Fix save_tmux_settings() data-loss bug

In `save_tmux_settings()` (lines 2739-2741), change:
```python
data = dict(self.config_mgr.project_config)
if tmux_data:
    data["tmux"] = tmux_data
```
To:
```python
data = dict(self.config_mgr.project_config)
if tmux_data:
    existing_tmux = dict(data.get("tmux") or {})
    existing_tmux.update(tmux_data)
    data["tmux"] = existing_tmux
```
This preserves `tmux.monitor` and any other sub-sections when saving schema-tracked fields.

### Part 2: Add git_tui to TMUX_CONFIG_SCHEMA

Add a new entry to `TMUX_CONFIG_SCHEMA` after `prefer_tmux`:
```python
"git_tui": {
    "summary": "Git management TUI",
    "detail": (
        "External git TUI to integrate in the TUI switcher. "
        "Detected installed tools shown as options. "
        "Set to 'none' to disable."
    ),
    "type": "enum",
    "options": "lazygit,gitui,tig,none",  # base options
    "default": "none",
},
```

The options could be dynamically built by calling `detect_git_tuis()` from agent_launch_utils at populate time, adding "none" as the last option and any non-installed tools greyed out or excluded. However, for simplicity, list all known options statically — the user can cycle through them and the TUI switcher (t507_4) will check if the tool is actually installed before launching.

### Part 3: Enhance populate to show detection info

In `_populate_tmux_tab()`, after rendering the git_tui field, optionally add a hint showing which tools are actually installed (call `detect_git_tuis()`).

## Verification Steps

1. Open `ait settings` → Tmux tab → verify `git_tui` field appears
2. Cycle through options with Enter — should show lazygit, gitui, tig, none
3. Save settings → verify `tmux.monitor` section is preserved in project_config.yaml
4. Change git_tui to "lazygit" → save → verify `tmux.git_tui: lazygit` in project_config.yaml

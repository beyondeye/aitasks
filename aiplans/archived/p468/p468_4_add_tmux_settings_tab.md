---
Task: t468_4_add_tmux_settings_tab.md
Parent Task: aitasks/t468_better_codeagent_launching.md
Sibling Tasks: aitasks/t468/t468_5_refactor_board_create_tmux.md, aitasks/t468/t468_6_update_docs_tmux_integration.md, aitasks/t468/t468_7_auto_launch_tuis_in_tmux.md
Archived Sibling Plans: aiplans/archived/p468/p468_1_*.md, aiplans/archived/p468/p468_2_*.md, aiplans/archived/p468/p468_3_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Add Tmux Settings Tab (t468_4)

## Overview

Add a "Tmux" tab to the `ait settings` TUI so users can configure tmux defaults stored in `project_config.yaml`. Replaces the original `use_for_create` setting with `prefer_tmux` (pre-select tmux tab in launch dialogs).

## Steps

### Step 1: Add `TMUX_CONFIG_SCHEMA` dict
- Added after `VALID_PROFILE_SKILLS` in `settings_app.py`
- Three settings: `default_session` (string), `default_split` (enum), `prefer_tmux` (bool)

### Step 2: Add TabPane to `compose()`
- Added `"Tmux"` to TabbedContent labels
- New `TabPane("Tmux", id="tab_tmux")` with `VerticalScroll(id="tmux_content")`

### Step 3: Add tab shortcut
- Added `"t": "tab_tmux"` to `_TAB_SHORTCUTS`

### Step 4: Add `_populate_tmux_tab()` call to `on_mount()`

### Step 5: Implement `_populate_tmux_tab()`
- Loads tmux section from project_config
- `default_session`: ConfigRow (editable string)
- `default_split`: CycleField with horizontal/vertical
- `prefer_tmux`: CycleField with false/true
- Save/Revert buttons

### Step 6: Implement `save_tmux_settings()`
- Reads widget values, builds tmux dict
- Merges into project_config and saves via ConfigManager

### Step 7: Implement `_revert_tmux_settings()`

### Step 8: Wire Enter key handler for `tmux_cfg_` rows
- Pushes EditStringScreen for string settings

### Step 9: Add `_handle_tmux_config_edit()` callback

### Step 10: Wire button handlers in `on_button_pressed`

### Step 11: Update tab hint footers to include `t`

### Step 12: Update `load_tmux_defaults()` in `agent_launch_utils.py`
- Changed `use_for_create` → `prefer_tmux` in defaults and parsing

## Final Implementation Notes
- **Actual work done:** Added Tmux tab with 3 configurable settings, updated `load_tmux_defaults()` to use `prefer_tmux` instead of `use_for_create`
- **Deviations from plan:** User requested replacing `use_for_create` with `prefer_tmux` during planning — the tmux tab will control which tab is pre-selected in launch dialogs (terminal vs tmux) rather than controlling whether create uses tmux
- **Issues encountered:** None
- **Key decisions:** Tmux settings stored in `project_config.yaml` under `tmux:` key, reusing existing `ConfigManager.save_project_settings()` for persistence
- **Notes for sibling tasks:** The `prefer_tmux` setting from `load_tmux_defaults()` should be read by `AgentCommandScreen` (or its callers) to set the initial tab. Task t468_5 is effectively replaced by t474 (create dialog). The `default_session` and `default_split` values are already consumed by `AgentCommandScreen` via `load_tmux_defaults()`.

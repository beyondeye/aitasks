---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [ui, settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-26 12:53
updated_at: 2026-03-29 09:12
completed_at: 2026-03-29 09:12
---

## Context

Child task 1 (t468_1) created shared `AgentCommandScreen` with tmux integration and `agent_launch_utils.py` with `load_tmux_defaults()`. The defaults are currently hardcoded fallbacks. This task adds a "Tmux" tab to `ait settings` TUI so users can configure tmux defaults.

## Key Files to Modify

1. **`.aitask-scripts/settings/settings_app.py`** — Main settings TUI application
   - Add `TabPane("Tmux", id="tab_tmux")` to `compose()` method (line ~1849-1859)
   - Add `"t": "tab_tmux"` to `_TAB_SHORTCUTS` dict (line ~313-319)
   - Add `_populate_tmux_tab()` method following `_populate_project_tab()` pattern
   - Add save/revert handlers for tmux settings
   - Add `TMUX_CONFIG_SCHEMA` dict with setting descriptions

2. **`aitasks/metadata/project_config.yaml`** — Add `tmux:` section:
   ```yaml
   tmux:
     default_session: aitasks
     default_split: horizontal
     use_for_create: false
   ```

## Reference Files for Patterns

- `.aitask-scripts/settings/settings_app.py:2434-2503` — `_populate_project_tab()` as template
- `.aitask-scripts/settings/settings_app.py:321-360` — `PROJECT_CONFIG_SCHEMA` for schema pattern
- `.aitask-scripts/settings/settings_app.py:504-620` — `ConfigManager` for config loading/saving
- `.aitask-scripts/lib/agent_launch_utils.py` — `load_tmux_defaults()` reads these settings

## Implementation Plan

1. Add `TMUX_CONFIG_SCHEMA` dict with entries:
   - `default_session`: summary="Default tmux session name", detail="Session name used when creating new tmux sessions from agent launch dialog (default: aitasks)"
   - `default_split`: summary="Default pane split direction", detail="Split direction when creating new pane in existing window: horizontal or vertical (default: horizontal)"
   - `use_for_create`: summary="Use tmux for task creation", detail="When enabled, launching aitask-create from ait board (n shortcut) will run in a tmux session instead of a new terminal window (default: false)"

2. Add `TabPane("Tmux", id="tab_tmux")` to compose() and `"t": "tab_tmux"` to shortcuts

3. Create `_populate_tmux_tab()` following project config tab pattern:
   - Load current values from `project_config.yaml` `tmux:` section
   - Mount `ConfigRow` widgets for each setting
   - For `default_split`: use `CycleField` with options ["horizontal", "vertical"]
   - For `use_for_create`: use `CycleField` with options ["true", "false"]
   - Mount save/revert buttons

4. Add save handler that writes `tmux:` section to `project_config.yaml`

## Verification Steps

1. Run `python .aitask-scripts/settings/settings_app.py` and verify Tmux tab appears
2. Change settings and save — verify `project_config.yaml` is updated
3. Revert — verify values reset to saved state
4. Run `python -c "from agent_launch_utils import load_tmux_defaults; from pathlib import Path; print(load_tmux_defaults(Path('.')))"` to verify settings are read correctly

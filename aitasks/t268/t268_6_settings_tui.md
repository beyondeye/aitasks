---
priority: medium
effort: high
depends: [t268_3]
issue_type: feature
status: Implementing
labels: [modelwrapper, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-01 09:00
updated_at: 2026-03-01 18:17
---

## Context

This is child task 6 of t268 (Code Agent Wrapper). It creates a Textual-based Settings TUI for centralized review and update of all aitasks configuration — code agent defaults, board settings, codebrowser settings, and model lists.

## Key Files

- **Create:** `aiscripts/settings/settings_app.py`
- **Create:** `aiscripts/aitask_settings.sh`
- **Modify:** `ait` (add `settings` dispatcher entry)

## Implementation Plan

### 1. Create `aiscripts/aitask_settings.sh`

Shell wrapper following the same pattern as `aitask_board.sh` and `aitask_codebrowser.sh`:
- Source lib files
- Check Python/Textual dependencies
- Launch `settings_app.py`

### 2. Create `aiscripts/settings/settings_app.py`

Textual-based TUI with:
- **Category navigation:** sidebar or tabs for config categories:
  - Code Agent Defaults (`codeagent_config.json`)
  - Board Settings (`board_config.json`)
  - Codebrowser Settings (`codebrowser_config.json`)
  - Model Lists (`models_*.json`)
- **Per-project vs per-user display:** Show per-project values with per-user overrides highlighted
- **Edit both layers:** Clear indication of which layer (project vs user) is being modified
- **Export:** Bundle all settings to a single file using `config_utils.export_all_configs()`
- **Import:** Restore settings from a file using `config_utils.import_all_configs()`

### 3. Add `settings` to `ait` dispatcher

Add entry: `settings) shift; exec "$SCRIPTS_DIR/aitask_settings.sh" "$@" ;;`

Update `show_usage()` to include settings command under TUI section.

## Verification Steps

1. `./ait settings` opens the Settings TUI
2. All config categories are browsable
3. Per-project and per-user values are distinguishable
4. Editing a user setting saves to `.local.json`
5. Editing a project setting saves to project config
6. Settings export creates a valid bundle file
7. Settings import restores from bundle correctly
8. Export/import round-trips without data loss

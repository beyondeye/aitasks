---
Task: t426_5_settings_tui_default_profiles_editing.md
Parent Task: aitasks/t426_default_execution_profiles.md
Sibling Tasks: aitasks/t426/t426_1_*.md, aitasks/t426/t426_2_*.md, aitasks/t426/t426_3_*.md, aitasks/t426/t426_4_*.md, aitasks/t426/t426_6_*.md
Archived Sibling Plans: aiplans/archived/p426/p426_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t426_5 — Settings TUI Default Profiles Editing

## Context

The settings TUI Project Config tab already renders all keys from `PROJECT_CONFIG_SCHEMA` using `ConfigRow` widgets. After t426_1 adds the `default_profiles` entry to the schema, it will render automatically. However, the dict value needs proper validation when edited.

## Steps

### 1. Add VALID_PROFILE_SKILLS constant (line 329)

Set of valid skill names used for rendering individual rows and structural validation.

### 2. Add ProfilePickerScreen modal (line 1530)

FuzzySelect-based modal for choosing an execution profile. Shows `<not set>` + all available profile names.

### 3. Update _populate_project_tab() (line 2409)

Instead of one ConfigRow for the whole dict, render a section header + one ConfigRow per skill, each showing current profile or `(not set)`.

### 4. Update on_key() handler (line 1946)

Route `project_dp_` rows to ProfilePickerScreen with profiles from `config_mgr.profiles`.

### 5. Update save_project_settings() (line 2470)

Collect `project_dp_` rows into `default_profiles` dict. Empty skills excluded; if all empty, key removed.

### 6. Add _handle_default_profile_pick() callback (line 2533)

Updates ConfigRow display after profile selection.

## Files Modified

- `.aitask-scripts/settings/settings_app.py`

## Final Implementation Notes
- **Actual work done:** Replaced raw YAML editing of `default_profiles` with per-skill ConfigRow rendering and FuzzySelect-based profile picker. Added `VALID_PROFILE_SKILLS` constant, `ProfilePickerScreen` modal, per-skill rendering in `_populate_project_tab()`, routing in `on_key()`, collection logic in `save_project_settings()`, and `_handle_default_profile_pick()` callback.
- **Deviations from plan:** Original plan called for raw YAML editing with post-save validation. User feedback during review requested a better UX: per-skill rows with fuzzy profile selection (similar to code agent/model picker). This structural approach makes validation unnecessary — invalid keys and non-string values are impossible.
- **Issues encountered:** None.
- **Key decisions:** Used `project_dp_` ID prefix for skill rows to distinguish from regular `project_cfg_` rows. Profile names loaded from `config_mgr.profiles` (already available in the app). `<not set>` option maps to empty string, which causes the skill to be excluded from the dict on save.
- **Notes for sibling tasks:** The `VALID_PROFILE_SKILLS` constant includes `qa` (9 skills total). `ProfilePickerScreen` follows the same pattern as `VerifyBuildPresetScreen` — future similar pickers can follow the same structure.

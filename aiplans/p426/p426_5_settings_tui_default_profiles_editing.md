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

### 1. Verify existing rendering

After t426_1 is complete, the `default_profiles` key should already appear in the Project Config tab via the existing `_populate_project_tab()` loop. The `_format_yaml_value()` function handles dicts by rendering them as compact YAML (e.g., `{pick: fast, fold: fast}`).

Launch `./ait settings`, navigate to Project Config tab (press `c`), and verify `default_profiles` appears with its summary hint.

### 2. Add validation for `default_profiles` editing

**File:** `.aitask-scripts/settings/settings_app.py`

Find where project config values are saved after editing (the save handler for ConfigRow edits in the Project Config tab). Add validation specifically for the `default_profiles` key:

```python
VALID_PROFILE_SKILLS = {
    "pick", "fold", "review", "pr-import", "revert",
    "explore", "pickrem", "pickweb",
}
```

When the user edits `default_profiles`:
1. Parse the edited string as YAML
2. If result is not a dict (or is None/empty string), accept it (clearing the value)
3. If result is a dict:
   - Validate all keys are in `VALID_PROFILE_SKILLS`
   - Validate all values are strings (profile names)
   - If invalid keys found, show error notification: "Invalid skill name(s): <names>. Valid: pick, fold, review, pr-import, revert, explore, pickrem, pickweb"
   - If invalid values found, show error notification: "Profile names must be strings"

The validation should happen in the save/apply handler, NOT blocking the edit itself. This matches how `verify_build` validation works (accepts list or string).

### 3. Verify

- `./ait settings` → Project Config → edit `default_profiles` → enter `{pick: fast, review: default}` → save → verify persisted to project_config.yaml
- Edit with invalid key → enter `{invalid_skill: fast}` → verify error notification
- Edit to empty → verify it clears the value
- Reload → verify persisted values reload correctly

## Files to Modify

- `.aitask-scripts/settings/settings_app.py` — add VALID_PROFILE_SKILLS constant and validation logic

## Reference Files

- `.aitask-scripts/settings/settings_app.py:302-319` — PROJECT_CONFIG_SCHEMA (t426_1 will have added `default_profiles`)
- `.aitask-scripts/settings/settings_app.py:322-330` — `_format_yaml_value()` for dict rendering
- `.aitask-scripts/settings/settings_app.py` — search for `verify_build` handling for validation pattern reference

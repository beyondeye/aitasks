---
Task: t393_contribution_add_verified_skill_stats_for_nondefault_skills.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

Contribution from beyondeye (issues #5 and #8) with two merged features for the settings TUI:
1. **Verified skill stats** — read-only section in the Agent tab showing top agent/model combos by verified score for skills that have no configured defaults
2. **verify_build preset editor** — multi-line TextArea editor for `verify_build` with fuzzy-searchable presets from a YAML file, plus docs link and preset name display

The contributor provided complete diffs based on framework version 0.10.0. The changes are well-structured and fit cleanly into the existing codebase patterns.

## Implementation Plan

### 1. Add `TextArea` import (~line 52)

In the `from textual.widgets import` block, add `TextArea` after `TabbedContent`.

**File:** `.aitask-scripts/settings/settings_app.py` (line 52)

### 2. Add preset helpers after `_safe_id` (~line 330)

After `_safe_id()` (line 329), before `_normalize_model_id()` (line 332), add:
- `_PRESETS_FILE` constant pointing to `verify_build_presets.yaml`
- `_BUILD_VERIFY_DOCS` URL constant
- `_load_verify_build_presets()` function
- `_match_preset_name()` function

### 3. Add `FuzzySelect.Highlighted` message class (~line 702)

After `FuzzySelect.Cancelled` (line 702), add a `Highlighted` message class that posts when the highlight changes.

### 4. Post `Highlighted` message in `on_input_changed` and `_update_highlight`

- In `on_input_changed` (after line 742, after `_render_options()`): post `Highlighted` if `self.filtered` is non-empty
- In `_update_highlight` (after line 787, after `scroll_visible()`): post `Highlighted` for current highlight

### 5. Add `EditVerifyBuildScreen` and `VerifyBuildPresetScreen` classes (~line 1305)

After `EditStringScreen` (ends at line 1305), before `NewProfileScreen` (line 1308), add:
- `EditVerifyBuildScreen` — modal with TextArea for multi-line YAML editing + "Load Preset" button
- `VerifyBuildPresetScreen` — modal with FuzzySelect for preset selection + preview panel

### 6. Add CSS rules (~line 1508)

After `.op-desc` CSS rule (line 1508), add:
- `#edit_textarea` sizing rules
- `#preset_preview` styling

### 7. Update project config editing handler (~line 1670-1678)

In the `on_config_row_focused`/Enter handler, branch on `verify_build` key to use `EditVerifyBuildScreen` with presets instead of `EditStringScreen`. Store `_editing_project_row_id`.

### 8. Add `_collect_non_default_skill_stats` method (~line 1798)

After `_get_all_providers_label` (ends line 1797), before `_populate_agent_tab` (line 1799), add the method that collects verified stats for skills not in operation defaults.

### 9. Add skill stats section in `_populate_agent_tab` (~line 1867)

After the operation descriptions loop (line 1866), before the footer label (line 1868), mount the "Verified Skill Stats" section using `_collect_non_default_skill_stats()`.

### 10. Update `_populate_project_tab` (~line 2020-2030)

- Load presets once before the loop
- Show preset name next to `verify_build` display value
- Store `formatted` value for `raw_value` instead of calling `_format_yaml_value` twice
- Add docs link label after `verify_build` row

### 11. Update `_handle_project_config_edit` (~line 2070-2085)

- Use stored `_editing_project_row_id` for row lookup (more robust than re-computing)
- Show preset name in display value for `verify_build`
- Include exception details in error notification

### 12. Create `verify_build_presets.yaml`

**File:** `.aitask-scripts/settings/verify_build_presets.yaml` (new file)

Create with common project type presets (Python, Node.js, Go, Rust, Hugo, etc.)

## Verification

1. Run `python -c "import ast; ast.parse(open('.aitask-scripts/settings/settings_app.py').read())"` to verify syntax
2. Run `python -c "import yaml; yaml.safe_load(open('.aitask-scripts/settings/verify_build_presets.yaml'))"` to verify YAML
3. Launch `./ait settings` and verify:
   - Agent tab shows "Verified Skill Stats" section at the bottom (if any non-default skills have stats)
   - Project Config tab shows preset name next to verify_build if matching
   - Project Config tab shows docs link under verify_build
   - Editing verify_build opens multi-line TextArea editor
   - "Load Preset" button opens fuzzy-searchable preset picker with preview

## Final Implementation Notes

- **Actual work done:** Applied the contributor's diffs from issues #5 and #8 to settings_app.py. Created verify_build_presets.yaml with 17 common project type presets. All 12 planned steps implemented as specified.
- **Deviations from plan:** None — the contributor's diffs applied cleanly to the current codebase.
- **Issues encountered:** None.
- **Key decisions:** Used the contributor's exact code changes. Created a comprehensive set of 17 build presets covering Python, Node.js, Go, Rust, Hugo, Shell, Java, Ruby, PHP, Elixir, and Make.

## Post-Implementation

- Step 9: Archive task, update linked issue (#8), handle folded issues (#5)

---
Task: t279_fixes_to_profiles_tab_in_ait_settings.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Refactor Profiles Tab in ait settings TUI (t279)

## Context

The Profiles tab in `ait settings` currently shows ALL profiles together in a flat scrollable list with all fields inline. This is poor UX — users can't easily switch between profiles, fields lack descriptions, and there's no way to create/delete profiles from the TUI.

## File to Modify

**`aiscripts/settings/settings_app.py`** — sole file; contains all TUI logic, widgets, CSS.

## Changes

### 1. Add field descriptions and grouping constants (after `PROFILE_SCHEMA`, ~line 89)

**`PROFILE_FIELD_INFO`** — dict mapping each field key to a tuple of `(short_desc, detailed_desc)`:
- `short_desc` — 1-line summary shown by default under each field
- `detailed_desc` — multi-line explanation shown when user presses `?` or `h` on a focused field

**Toggle behavior:** Pressing `?`/`h` on a focused field toggles between short and detailed descriptions.

**`PROFILE_FIELD_GROUPS`** — ordered list of `(group_label, [field_keys])` for logical grouping:
- Identity: name, description
- Task Selection: skip_task_confirmation, default_email
- Branch & Worktree: create_worktree, base_branch
- Planning: plan_preference, plan_preference_child, post_plan_action
- Exploration: explore_auto_continue
- Lock Management: force_unlock_stale
- Remote Workflow: done_task_action, orphan_parent_action, complexity_action, review_action, issue_action, abort_plan_action, abort_revert_status

### 2. Add two new modal screens (after `EditStringScreen`, ~line 601)

- **`NewProfileScreen`** — filename input + base profile selector + Create/Cancel
- **`DeleteProfileConfirmScreen`** — confirmation dialog + Delete/Cancel

### 3. Add instance state (in `__init__`, ~line 680)

- `_selected_profile: str | None`
- `_expanded_field: str | None`

### 4. Rewrite `_populate_profiles_tab()` (replace lines 1035-1099)

New layout: explanation text, keyboard hints, profile selector CycleField, grouped fields with descriptions, Save + Delete buttons.

### 5. Handle profile selector changes (new `on_cycle_field_changed`)

### 6. Extend button handler (`on_button_pressed`)

### 7. Add callback methods (_handle_new_profile, _handle_delete_profile)

### 8. Update `_save_profile()` with repop counter

### 9. Update profile string edit handling with repop counter

### 10. Add `?`/`h` key handler for field detail toggle

## Verification

1. Run `./ait settings` → Profiles tab
2. Verify explanation + skills list
3. Profile selector cycling
4. Grouped fields with descriptions + `?` toggle
5. Save/edit fields
6. Create/delete profiles
7. Other tabs still work

## Final Implementation Notes
- **Actual work done:** Refactored the Profiles tab from a flat all-profiles view to a profile-selector UX with grouped fields, two-level descriptions (short/detailed via `?` key), create/delete profile modals, and focus restoration after repopulation.
- **Deviations from plan:** Added `_profiles_focus_target` and `_focus_widget_by_id()` + `call_after_refresh` pattern to fix focus loss when repopulating the tab (discovered during user testing). Used `?` key only (removed `h` key trigger to avoid conflicts).
- **Issues encountered:** Focus was lost after `remove_children()` + remount when cycling profiles or toggling `?`. Fixed by passing a `focus_widget_id` parameter to `_populate_profiles_tab()` and using `call_after_refresh` to restore focus.
- **Key decisions:** Used `_repop_counter` suffix on all widget IDs (same pattern as agent tab) to prevent Textual duplicate ID errors during async removal.

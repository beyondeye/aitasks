---
priority: medium
effort: medium
depends: [t777_15]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:01
updated_at: 2026-05-17 12:01
---

## Context

Depends on foundation (t777_1..5) and is INDEPENDENT of per-skill conversions (can be implemented in parallel with t777_6..15).

Extracts the profile-field-editing screens out of `.aitask-scripts/settings/settings_app.py` into a reusable `lib/profile_editor.py` module. The extracted widget is then consumed by `ait settings` (current consumer) AND by the `AgentCommandScreen` per-run UI (t777_17, next child).

Pure refactor — no behavior change to `ait settings`. Regression test: walk through profile editing in `ait settings` and confirm identical UX.

## Key Files to Modify

- `.aitask-scripts/lib/profile_editor.py` (new) — extracted module
- `.aitask-scripts/settings/settings_app.py` (modify) — import from the new module instead of defining inline

## Reference Files for Patterns

- `.aitask-scripts/settings/settings_app.py` line 1073 (`EditValueScreen`) — the primary widget to extract
- Surrounding field-edit infrastructure (search for `class .*ProfileScreen` and `class ProfilePickerScreen` around line 1256, `class NewProfileScreen` around line 1294)
- `.aitask-scripts/lib/agent_command_screen.py` — pattern for a reusable `ModalScreen` exposed by `lib/`

## Implementation Plan

1. Identify the exact set of classes/functions to extract: `EditValueScreen`, `ProfilePickerScreen`, `NewProfileScreen`, plus any helpers they depend on (field-info constants, group definitions in `settings_app.py` lines 95-355).
2. Decide on the public API:
   ```python
   # lib/profile_editor.py
   class ProfileEditScreen(ModalScreen):
       """Edit a profile's fields in a sub-modal."""
       def __init__(self, profile_data: dict, on_save: callable, *, title: str = "Edit Profile"):
           ...
   ```
3. Move the classes to `lib/profile_editor.py`, fix imports, preserve their public method names.
4. In `settings_app.py`, import from the new module: `from profile_editor import ProfileEditScreen, ...`.
5. Manual regression test: launch `ait settings`, navigate to a profile, edit a field, save, confirm the YAML on disk reflects the edit.

## Verification Steps

1. `ait settings` launches without error.
2. Profile-editing UX in `ait settings` is byte-identical to pre-refactor behavior.
3. `from profile_editor import ProfileEditScreen` works from a fresh Python script.
4. `shellcheck` clean (only relevant if any new shell scripts are added; this child is mostly Python).
5. Test (manual): edit a profile field, save, confirm change in the YAML file.

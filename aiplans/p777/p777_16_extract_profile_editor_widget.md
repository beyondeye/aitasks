---
Task: t777_16_extract_profile_editor_widget.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_16 — Extract profile-editor widget to `lib/profile_editor.py`

## Scope

Pure refactor. Extract `EditValueScreen` + `ProfilePickerScreen` + `NewProfileScreen` + supporting field-info constants from `settings_app.py` into reusable `lib/profile_editor.py`. Consumed by `ait settings` (existing) and `AgentCommandScreen` (t777_17).

Regression test: walk through `ait settings` profile editing manually — byte-identical UX before and after.

## Step Order

1. Identify extraction set: classes around `settings_app.py` lines 1073, 1256, 1294; supporting constants in lines 95–355.
2. Move to `lib/profile_editor.py` preserving public method names.
3. Update `settings_app.py` to import from the new module.
4. Manual regression test in `ait settings`.

## Critical Files

- `.aitask-scripts/lib/profile_editor.py` (new)
- `.aitask-scripts/settings/settings_app.py` (modify — replace inline classes with imports)

## Public API

```python
class ProfileEditScreen(ModalScreen):
    def __init__(self, profile_data: dict, on_save: callable, *, title: str = "Edit Profile"):
        ...
```

## Pitfalls

- **Behavior parity** — settings TUI is the existing consumer; any change in UX is a regression. Walk through every editable field type.
- **Imports** — settings_app.py also imports field-info constants; keep them accessible (re-export from `lib/profile_editor.py` or move to a shared `lib/profile_schema.py`).

## Verification

`ait settings` profile editing works identically post-refactor; `from profile_editor import ProfileEditScreen` works from a fresh script.

---
priority: medium
effort: medium
depends: [t777_16]
issue_type: feature
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:01
updated_at: 2026-05-17 12:01
---

## Context

Depends on t777_5 (wrapper supports `--profile-override`) and t777_16 (reusable `ProfileEditScreen`). Adds the per-run profile editing UI to the `AgentCommandScreen` (the existing modal dialog shown when launching a skill from a Python TUI like `ait board`).

When the user opens the launch dialog and clicks (E)dit on the Profile row, a sub-modal opens with the resolved profile's editable fields. Saving the sub-modal writes a one-shot override YAML; the dialog's `full_command` and `prompt_str` reactives update to launch through `ait skillrun --profile-override <path>`.

## Key Files to Modify

- `.aitask-scripts/lib/agent_command_screen.py` (modify) — add Profile row + (E)dit button + sub-modal hook
- Confirm `aitask_skillrun.sh` (t777_5) already accepts `--profile-override` — if not, add it here

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_command_screen.py` `compose()` ~line 251 and `on_mount()` ~line 300 — existing Agent row that we mirror for the Profile row
- `.aitask-scripts/lib/profile_editor.py` (from t777_16) — the sub-modal we push
- `.aitask-scripts/board/aitask_board.py` ~line 3891 — example of how AgentCommandScreen is instantiated, to confirm where the new option appears

## Implementation Plan

1. Modify `AgentCommandScreen.__init__` to accept `default_profile: str | None = None` and `skill_name: str | None = None`.
2. In `compose()`, add a "Profile" row above the existing "Agent" row:
   ```python
   with Horizontal(id="profile_row"):
       yield Label(f"Profile: {self.current_profile_name}", id="profile_row_label")
       yield Button("(E)dit", variant="primary", id="btn_edit_profile")
   ```
3. Add a keybinding for `e` to trigger Edit Profile.
4. Add `action_edit_profile` method:
   ```python
   def action_edit_profile(self):
       def on_save(updated_profile):
           # Write override YAML
           override_path = f"/tmp/ait-run-override-{os.getpid()}.yaml"
           write_yaml(override_path, updated_profile)
           self._profile_override_path = override_path
           self._refresh_command()  # rebuild full_command/prompt_str
       self.app.push_screen(ProfileEditScreen(self.current_profile_data, on_save))
   ```
5. Update `_refresh_command()` (or equivalent reactive watcher) to construct:
   ```python
   if self._profile_override_path:
       self.full_command = f"ait skillrun {skill} --profile-override {path} {args}"
   else:
       self.full_command = original_full_command
   ```
6. Update callers in `aitask_board.py` (and any other AgentCommandScreen instantiators) to pass `skill_name` and `default_profile`.

## Verification Steps

1. `ait board` → select a task → launch → AgentCommandScreen shows Profile row with (E)dit button.
2. Click (E)dit (or press `e`) → ProfileEditScreen opens with current profile fields.
3. Modify a field, Save → AgentCommandScreen updates `full_command` to `ait skillrun pick --profile-override <path> <args>`.
4. Run via "Run in terminal" — confirm `ait skillrun` is invoked with the override and the agent receives the updated profile in the rendered skill.
5. The override YAML is deleted after the wrapper consumes it (t777_5 behavior — confirm here).

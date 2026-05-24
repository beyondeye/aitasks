---
Task: t777_16_extract_profile_editor_widget.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_27_recover_runtime_skills_and_parity_tests.md, aitasks/t777/t777_28_dedup_template_branches_common_proc_and_macros.md
Archived Sibling Plans: aiplans/archived/p777/p777_10_convert_aitask_fold.md, aiplans/archived/p777/p777_11_convert_aitask_qa.md, aiplans/archived/p777/p777_12_convert_aitask_pr_import.md, aiplans/archived/p777/p777_13_convert_aitask_revert.md, aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-24 17:33
---

# Plan: t777_16 — Extract profile-editor widget to `lib/profile_editor.py`

## Context

Part of t777 (modular pick skill redesign). The parent goal: refactor the
profile-editing code in `ait settings` into **common code** that can also edit
execution-profile variables *per skill run* — the next child, **t777_17**,
adds a per-run profile `(E)dit` modal to `AgentCommandScreen` and needs a
reusable `ProfileEditScreen(ModalScreen)` with an `on_save` callback.

**Plan revised during verification (2026-05-20).** The original plan and task
description assumed a single `EditValueScreen`/`ProfileEditScreen` class
existed in `settings_app.py` to extract as a pure refactor. It does **not**:

- There is **no `ProfileEditScreen` modal**. Profile editing in `ait settings`
  is rendered *inline in a tab* by `_populate_profiles_tab()`, tightly coupled
  to `SettingsApp` state.
- The existing pieces are constants, two field widgets, and one field-edit
  modal — listed below.
- t777_17 needs a real modal, which must be **built new**, not extracted.

Approach (confirmed with user): **shared renderer**. Move the reusable
primitives to `lib/profile_editor.py`, add a shared field-rendering
generator + value-collector, and a new `ProfileEditScreen(ModalScreen)`.
`ait settings` keeps its inline Profiles tab but delegates field rendering to
the shared helper — UX of `ait settings` is unchanged.

**Re-verified 2026-05-24.** All referenced symbols still present; the only
drift is line-number shift in two methods (corrected below). Independence
from sibling t777_15 reconfirmed.

## Critical Files

- `.aitask-scripts/lib/profile_editor.py` — **new** module
- `.aitask-scripts/settings/settings_app.py` — remove moved symbols, import
  them back from the new module, delegate rendering/collection to helpers

## What moves to `lib/profile_editor.py`

Moved verbatim from `settings_app.py` (no logic change):

| Symbol | Current location | Kind |
|--------|------------------|------|
| `_UNSET` | line 126 | constant |
| `PROFILE_SCHEMA` | lines 95-124 | constant |
| `PROFILE_FIELD_INFO` | lines 169-353 | constant |
| `PROFILE_FIELD_GROUPS` | lines 356-378 | constant |
| `CycleField` | lines 711-801 | widget (`Static`) |
| `ConfigRow` | lines 803-841 | widget (`Static`) |
| `EditStringScreen` | lines 1072-1104 | modal (`ModalScreen`) |

**Stays in `settings_app.py`** (not needed by the per-run editor): the
profile-*management* modals `ProfilePickerScreen` (line 1256), `NewProfileScreen`
(line 1294), `SaveProfileConfirmScreen` (line 1384),
`DeleteProfileConfirmScreen` (line 1351); and the project-config editors
`EditVerifyBuildScreen` (line 1106), `VerifyBuildPresetScreen` (line 1195)
(`verify_build` is a project-config field, not a profile field).

`CycleField`/`ConfigRow` are also used by other settings tabs (board tab
`_populate_board_tab` line 2214+, project, tmux) and `ExportScreen.compose()`
line 847+ — those keep working via the re-import.

## New code in `lib/profile_editor.py`

1. **`compose_profile_fields(profile_data, *, id_prefix, expanded_field=None)`**
   — generator yielding the grouped field widgets + description labels.
   Extracted from the loop at `settings_app.py:2784-2847`. Builds widget IDs
   with the **exact existing scheme** so the Enter-key handler and value
   collection stay compatible:
   - bool/enum → `CycleField`, id `profile_{key}__{id_prefix}`
   - string → `ConfigRow`, id `profile_str_{key}__{id_prefix}`
   - int → `ConfigRow`, id `profile_int_{key}__{id_prefix}`
   - description label uses `expanded_field` to pick short vs long text.

2. **`collect_profile_values(query_one, base_data, *, id_prefix)`**
   → `(updated_data: dict, errors: list[str])`. Extracted from
   `_save_profile` at `settings_app.py:2953-3012` (reads each widget by id,
   applies bool/enum/string/int coercion, `_UNSET` → key removed, negative /
   non-int → appended to `errors` instead of `self.notify`). Caller does the
   `notify`.

3. **`ProfileEditScreen(ModalScreen)`** — public API for t777_17:
   ```python
   class ProfileEditScreen(ModalScreen):
       def __init__(self, profile_data: dict, on_save, *, title: str = "Edit Profile"):
   ```
   - `compose()`: titled `Container` → `VerticalScroll` with
     `yield from compose_profile_fields(profile_data, id_prefix="modal")`,
     plus Save / Cancel buttons.
   - Enter on a `profile_str_`/`profile_int_` row → push `EditStringScreen`
     (same as settings).
   - Save → `collect_profile_values(self.query_one, profile_data, id_prefix="modal")`;
     on errors `self.app.notify(...)` and stay open; else call
     `on_save(updated)` and `self.dismiss(updated)`.
   - `escape` cancels (`dismiss(None)`).
   - Module sets up `sys.path` for `lib/` like `agent_command_screen.py`
     (`agent_command_screen.py:42-44`).

## Step Order

1. Create `lib/profile_editor.py`: module docstring + `sys.path` shim +
   textual imports; paste the 4 constants and `CycleField`, `ConfigRow`,
   `EditStringScreen` verbatim.
2. Add `compose_profile_fields()` + `collect_profile_values()`, factored
   from the existing tab loop and `_save_profile`.
3. Add `ProfileEditScreen(ModalScreen)`.
4. In `settings_app.py`: delete the moved definitions; add
   `from profile_editor import (_UNSET, PROFILE_SCHEMA, PROFILE_FIELD_INFO,
   PROFILE_FIELD_GROUPS, CycleField, ConfigRow, EditStringScreen,
   ProfileEditScreen, compose_profile_fields, collect_profile_values)`.
5. Rewrite `_populate_profiles_tab()` field loop (the inner loop currently at
   lines 2784-2847 of the method spanning 2697-2878) to
   `for w in compose_profile_fields(data, id_prefix=f"{safe_fn}_{rc}",
   expanded_field=self._expanded_field): container.mount(w)`.
6. Rewrite `_save_profile()` (`2953-3012`) to call
   `collect_profile_values(self.query_one, ..., id_prefix=f"{safe_fn}_{rc}")`,
   then `self.notify` each returned error, then `config_mgr.save_profile`.
7. Verify the profile-string Enter handler (~`settings_app.py:1759`) still
   matches — it keys off the unchanged `profile_str_`/`profile_int_` id
   prefixes, so no change expected; confirm during testing.

## Pitfalls

- **ID scheme must stay byte-identical** — `_save_profile` reconstruction and
  the Enter-key handler parse `profile_{key}__…`, `profile_str_…`,
  `profile_int_…`. Keep `id_prefix=f"{safe_fn}_{rc}"` in settings so nothing
  downstream changes.
- **Circular import** — `profile_editor.py` must not import `settings_app`.
  `_safe_id` stays in settings (caller computes `id_prefix`).
- **`ConfigRow` is used widely** — board/project/tmux tabs + `ExportScreen`.
  The move is mechanical; the re-import keeps all of them working. Test
  those tabs too.
- **int validation** — moved into `collect_profile_values` as returned
  `errors`; the `self.notify` calls stay in the settings caller.

## Verification

1. `ait settings` launches; Profiles tab renders identically. Cycle a
   bool/enum field; press Enter on a string field → `EditStringScreen` opens
   → save; press `?` to toggle field detail; Save profile → confirm the YAML
   under `aitasks/metadata/profiles/` reflects the edit; Revert + Delete
   still work.
2. Board / Project / Tmux tabs and Export modal still render and edit
   (regression check for the `CycleField`/`ConfigRow` move).
3. `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); \
   from profile_editor import (ProfileEditScreen, compose_profile_fields, \
   collect_profile_values, CycleField, ConfigRow, EditStringScreen, \
   PROFILE_SCHEMA, PROFILE_FIELD_GROUPS)"` succeeds.
4. Smoke-mount `ProfileEditScreen` (full per-run UX is exercised by t777_17).

See **Step 9 (Post-Implementation)** of the task workflow for cleanup,
archival, and merge.

## Notes for sibling tasks (t777_17)

- Import the modal as `from profile_editor import ProfileEditScreen`.
- Construct it `ProfileEditScreen(current_profile_data, on_save)`; `on_save`
  receives the updated profile dict, and the screen also `dismiss()`es with
  that dict for callback-style use.
- The module already does its own `sys.path` shim, so importing it from
  `agent_command_screen.py` needs no extra path setup.

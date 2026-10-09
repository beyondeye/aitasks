---
Task: t1930_fix_settings_reload_duplicate_ids.md
Base branch: main
Output branch: main
---

# t1930 — Fix Settings `r` (reload all) DuplicateIds crash

## Context

Pressing `r` in `ait settings` runs `_reload_all_configs`
(`.aitask-scripts/settings/settings_app.py:4427`), which repopulates every tab
back to back. Each `_populate_*_tab` calls `container.remove_children()`, which
is deferred (async), then mounts the new widgets right away. Any **fixed** widget
id mounted directly into the container collides with the copy that has not been
removed yet, and Textual raises `DuplicateIds`. The other tabs avoid this with the
`_repop_counter` id suffix (Agent / Board / Project / Tmux), or by clearing in
place (Project Groups / Shortcuts). Models mounts no ids.

Reproduced on HEAD with a scratch script: the crash happens **only when the
project has no execution profiles**. In that case `_populate_profiles_tab` takes
its empty-state branch and mounts `Button(id="btn_profile_add_new")` (line ~3712)
directly into `#profiles_content`. With at least one profile, every
direct-child id in that tab already carries the `rc` suffix
(`cf_profile_selector_{rc}`, `profiles_search_{rc}`, `profiles_params_scroll_{rc}`,
`profiles_buttons_{rc}`), and `r` works. The `btn_profile_save__/revert__/delete__`
buttons live inside the rc-suffixed `Horizontal`, so they are under a different
parent and do not collide. The same collision also hits any other empty-to-empty
repopulate of the Profiles tab, not just `r`.

## Implementation

### 1. `.aitask-scripts/settings/settings_app.py` — suffix the add-new button id

- In `_populate_profiles_tab`'s empty-profiles branch, change
  `id="btn_profile_add_new"` → `id=f"btn_profile_add_new_{rc}"` (the `rc` local
  is already bound above it). Add a short comment matching the existing
  "remove_children() is deferred" comments.
- In the button handler (line ~4068), change
  `elif btn_id == "btn_profile_add_new":` →
  `elif btn_id.startswith("btn_profile_add_new"):`, the same prefix-match idiom
  the handler already uses for `btn_profile_save__`, `btn_board_save`, etc.
  Nothing else references the id (grepped the repo and tests).

### 2. New regression test `tests/test_settings_reload_all.py`

unittest + `App.run_test`, modelled on `tests/test_settings_superseded_models.py`
(the same tmp-cwd fixture, `keybinding_registry._reset_for_tests()`,
`refresh_label_case()`, `commit_metadata` stub, `_run_projects_group` stub):

- Fixture: `aitasks/metadata/` holding `userconfig.yaml` + `codeagent_config.json`
  (the shape the task names); a variant adds `profiles/fast.yaml`.
- `test_reload_without_profiles_keeps_running`: boot `SettingsApp` at (140, 60),
  press `r` **twice** (two reloads catch a leak that only shows up on the second
  remount), `pilot.pause()`, then assert:
  - `app.is_running` and no exception escaped `run_test` (Textual re-raises
    `DuplicateIds` on exit from `run_test`, so reaching the asserts plus a clean
    exit is the signal);
  - every tab repopulated: `_repop_counter` went up, and each of
    `#agent_content`, `#board_content`, `#project_content`, `#tmux_content`,
    `#models_content`, `#profiles_content`, `#shortcuts_content`,
    `#project_groups_content` has children once removals settle;
  - `#profiles_content` holds **exactly one** `Button` whose id starts with
    `btn_profile_add_new` (the old copies really went away);
  - the "Configs reloaded from disk" notification fired.
- `test_reload_with_profile_keeps_running`: the same with one profile, asserting
  exactly one `profiles_buttons_*` container afterwards. This path already passes;
  it pins it.
- `test_add_new_button_still_opens_dialog`: after `r`, click/press the suffixed
  button and assert `NewProfileScreen` is pushed, so the handler's prefix match is
  covered.
- **Red proof:** run the new test against the unfixed file (revert the 2-line
  edit only in a scratch copy, never by `git stash`/`git restore` in the shared
  tree) and confirm `test_reload_without_profiles_keeps_running` fails with
  `DuplicateIds`.

### 3. Deliberately not changed

t1921's "fix the file, then reopen Settings" message (line ~2843) stays as it is.
It fires when a code-agent config file is **unreadable**. `r` calls
`config_mgr.load_all()`, and `action_reload_configs` catches nothing, so pointing
the user at `r` in that state would probably swap one error for a crash. That
test asserts `"press r"` is absent (`tests/test_settings_superseded_models.py:576`).
During implementation I will check whether `r` on a malformed config crashes. If
it does, I will record it under "Upstream defects identified" instead of widening
this task.

## Verification

- `python3 tests/test_settings_reload_all.py` passes; the red proof fails on the
  unfixed copy.
- Neighbouring settings modules still pass: `tests/test_settings_superseded_models.py`,
  `test_settings_shortcuts_tab.py`, `test_settings_project_groups_tab.py`,
  `test_settings_commit_on_save.py`, `test_settings_default_profiles_unknown_keys.py`.
- Real terminal (handed to the user at Step 8 review): run `ait settings` in a
  project with no profiles, press `r` a few times, open Execution Profiles and
  activate "Create New Profile". Then press `r` in this repo, which has profiles.
  The app stays up in both.

## Step 9

Post-implementation: current-branch mode, so no merge. Archive with
`./.aitask-scripts/aitask_archive.sh 1930`, then `./ait git push`.

## Risk

### Code-health risk: low
None identified. A two-line change in one tab, using the id-suffix and
prefix-match idioms the file already uses. The only consumer of the id is the
handler being edited.

### Goal-achievement risk: low
None identified. The root cause was reproduced (the crash needs the no-profiles
fixture) and the regression test asserts the exact failure mode.

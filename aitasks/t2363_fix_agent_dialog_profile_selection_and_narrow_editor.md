---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tui, minimonitor, execution_profiles, agent_command_dialog]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-11-25 18:32
updated_at: 2026-11-25 18:37
---

## Symptom (user report)

Opening the pick launch dialog from **minimonitor** (narrow ~40-col companion
pane) to run `/aitask-pick` with a different execution profile:

1. There is **no option to change / select the execution profile** — only an
   `(E)dit` button for editing the current one.
2. `(E)dit` opens a **very narrow profile-editor dialog** that is unusable.
3. The editor has **no horizontal scroll**, so clipped field content cannot be
   reached.

## Root causes (from exploration)

### 1. No profile selector in `AgentCommandScreen`

`.aitask-scripts/lib/agent_command_screen.py`

- `compose()` (~:496-503) renders `#profile_row` as `Label("Profile: <name>")`
  + a single `(E)dit` button (`btn_edit_profile`, keys `e/E`). Nothing lets the
  user pick another profile (`default` / `fast` / `remote` / local ones).
- The override plumbing already exists: `_build_command_args()` (~:969-980)
  prepends `--profile <self._profile_override_name>` and
  `_apply_profile_override()` re-resolves the command via
  `resolve_dry_run_command`. Today it is only fed by the one-shot
  `_skillrun_<unique>` path (`_on_profile_saved_one_shot`).
- Profile list source: `./.aitask-scripts/aitask_scan_profiles.sh`
  (`PROFILE|<file>|<name>|<description>` lines, local/ shadows project/).

### 2. `ProfileEditScreen` has no narrow mode

`.aitask-scripts/lib/profile_editor.py`

- `DEFAULT_CSS` (~:852-898): `#profile_edit_dialog { width: 80%; height: 90%;
  border: thick; padding: 1 2; }` with no `narrow` variant. In a ~40-col
  pane this leaves ~26 content columns.
- `AgentCommandScreen` (`narrow=` ctor flag → `.narrow` CSS class) and
  `AgentModelPickerScreen` (`lib/agent_model_picker.py` ~:353) both already
  implement a narrow mode (width 100%, round border, trimmed padding) —
  `action_edit_profile()` (~:1012) does not forward `self._narrow` to the
  editor.
- The help line (`#profile_edit_help`, height 1) is a long single line that is
  clipped in narrow panes.

### 3. Single-line rows, no horizontal overflow

- `CycleField.render()` (~:475-488) renders `label:  ◀ opt1 | opt2 | … ▶` on one
  line; `ConfigRow` renders `[PROJECT]  key:  value` on one line. Both are
  `height: 1` inside `_NoArrowsVerticalScroll` (~:98), which hides x-overflow
  and has left/right scroll bindings removed (they are used for cycling).
  Result: long option lists / values are truncated and unreachable.
- Fix direction (to decide in planning): in narrow mode render the label on its
  own line and only the **current** option (`◀ value ▶`) or wrap the options
  (`height: auto`); `CycleField._option_index_at()` maps click x-offsets to
  options and must stay consistent with whatever layout is chosen. Adding an
  x-scrollbar alone is a poor fit because left/right are cycle keys.
- `CycleField` / `ConfigRow` are shared with the settings TUI's Profiles tab
  (SettingsApp has equivalent App-level CSS — keep both surfaces consistent;
  see the comment in `ProfileEditScreen.DEFAULT_CSS`).

### 4. Side defect: profile paths are cwd-relative, not `project_root`

`agent_command_screen.py:81-82` — `_PROFILES_DIR = Path("aitasks/metadata/profiles")`
and `_LOCAL_PROFILES_DIR` are relative to the process cwd. Load
(`_load_active_profile_data`), persistent save, one-shot save, the
`_skillrun_*` prune and the `./.aitask-scripts/aitask_skill_rerender.sh` call
all ignore `self._project_root`. When minimonitor/monitor opens a pick dialog
for a task in **another** project (`build_pick_screen(target_root, …)`,
`minimonitor_app.py` ~:4453), the editor reads and writes the wrong
project's profiles.

## Required changes

1. Add a **profile selector** to `AgentCommandScreen`'s profile row (e.g. a
   `(S)elect`/`Profile` button + key, or make the row a `Select`), listing
   profiles from `aitask_scan_profiles.sh` for `self._project_root`. Choosing a
   profile sets the override so the command becomes `--profile <name>`, updates
   the row label, and re-resolves the command. Choosing the resolved default
   clears the override. Pick an unused key (check `BINDINGS` and `on_key`,
   and t1296 for the existing key-collision issue).
2. Make the edit flow follow the selection: `(E)dit` loads the **selected**
   profile; a persistent save writes to the **selected** profile, not
   `default_profile` (today `_on_profile_saved_persistent` uses
   `self.default_profile or self.current_profile_name`, which would be wrong
   after a switch); `_clear_one_shot_override` falls back to the selected profile.
   Keep the distinction between a real profile name and a `_skillrun_*` one-shot
   override (`_load_active_profile_data` currently looks up the override name
   only under `profiles/local/`).
3. Give `ProfileEditScreen` a `narrow` mode (ctor flag → CSS class, mirroring
   `AgentCommandScreen` / `AgentModelPickerScreen`); forward `narrow=self._narrow`
   from `action_edit_profile`. In narrow mode: full width, compact chrome, a
   wrapped or shortened help line, and field rows whose content stays reachable
   (see root cause 3).
4. Resolve every profile path and the rerender helper against
   `self._project_root` (root cause 4).
5. The selector itself must work in narrow mode (the minimonitor pane).

## Tests

- Extend `tests/test_agent_command_dialog_narrow.py` (narrow profile row +
  selector) and add coverage for: selecting a profile → command contains
  `--profile <name>`; selecting the default → no `--profile`; edit/save target
  the selected profile; profile paths resolve under a non-cwd `project_root`.
- `ProfileEditScreen` narrow-mode test at ~40 cols: every CycleField's current
  value is visible (not clipped). Existing profile-editor tests:
  `tests/test_profile_editor_*.py`.
- Follow `aidocs/framework/testing_conventions.md` for `App.run_test` +
  `@work` workers.

## Docs

The website docs for the pick dialog / minimonitor may mention the profile row
— update them to describe the selector (run `website/check_links.py` after
editing).

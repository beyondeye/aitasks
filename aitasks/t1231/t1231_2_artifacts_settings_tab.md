---
priority: medium
effort: medium
depends: [t1231_1]
issue_type: feature
status: Ready
labels: [ait_settings, task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-07-26 22:58
updated_at: 2026-07-26 22:58
---

Add an **Artifacts** tab to the settings TUI so the artifact backend registry
(`artifacts:` in `aitasks/metadata/project_config.yaml`) is editable without
hand-editing YAML — in particular the `gitbranch` backend added by t1231_1.

**Full design + rationale: `aiplans/archived/p1231_configurable_git_branch_artifact_backend.md`
(parent plan, §t1231_2).**

## Context

`aitasks/metadata/project_config.yaml` currently has **no `artifacts:` section at
all** — `artifacts.default_backend` resolves to `local` through the "absent"
path. t1231_1 adds the `gitbranch` adapter, and configuring it by hand means
writing a nested two-level YAML block correctly. This task makes it a pane.

The nested-section write pattern is already established by the **Tmux tab**
(`TMUX_CONFIG_SCHEMA` + `save_tmux_settings`, `settings_app.py:2846-2966`) —
copy it, do not invent a new one.

## Depends on t1231_1

t1231_1 adds two `artifact_registry.py` subcommands this pane requires:
- **`adapters`** — prints `local` + `sorted(KNOWN_ADAPTERS)`, i.e. the
  *available* adapters independent of config. The existing `cmd_list`
  (`artifact_registry.py:149-154`) prints only *registered* backends, so on a
  fresh project `gitbranch` is unlistable and could never be selected to create
  its own first configuration. **The selector must use `adapters`, not `list`.**
- **`validate-ref <name>`** — exit 0/1 + message, so the pane validates a branch
  name *before* the backend is registered.

## Key files to modify

`.aitask-scripts/settings/settings_app.py` — six registration touch-points, all
verified present:

1. `_TAB_SWITCH_ACTIONS` (L172-181) — add `"switch_tab_artifacts": "tab_artifacts"`.
   Insertion order drives the footer-hint order.
2. `BINDINGS` (L1509-1516) — add `Binding("<key>", "switch_tab_artifacts", "Artifacts tab", show=False)`.
   **Only `k`, `o`, `z` are unbound** — `a b c d e f g h i j l m n p q r s t u v
   w x y` and `?` are all taken (`j` = TUI switcher via
   `TuiSwitcherMixin.SWITCHER_BINDINGS`, `?` = shortcut editor via
   `ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS`). **Recommended: `k`.**
   Re-verify against live `BINDINGS` at implementation time — main advances.
3. `action_switch_tab_artifacts()` stub near L1706-1728, body
   `self._switch_to_tab("tab_artifacts")`.
4. `compose()` (L1573-1603) —
   `TabPane(self.label("switch_tab_artifacts", "Artifacts"), id="tab_artifacts")`
   wrapping `VerticalScroll(id="artifacts_content")`.
5. `on_mount()` (L1605-1613) — call `self._populate_artifacts_tab()`.
6. Footer hint — **nothing to do**; `_tab_switch_hint()` (L1730-1743) derives
   from `_TAB_SWITCH_ACTIONS` automatically.

## Pane contents

New `ARTIFACTS_CONFIG_SCHEMA` (module level, beside `TMUX_CONFIG_SCHEMA`) with:
- `default_backend` — a `CycleField` whose options come from
  `artifact_registry.py adapters` (subprocess, see below).
- `backends.gitbranch.branch` — a `ConfigRow`, default `aitask-artifacts`.

`_populate_artifacts_tab()` / `save_artifacts_settings()` /
`_revert_artifacts_settings()` / `_handle_artifacts_config_edit()` mirror the
tmux quartet. Save merges into `data["artifacts"]`, drops the section when it
becomes empty, then `save_project_settings` → `load_all` → repopulate.

**Self-consistency:** selecting `gitbranch` as `default_backend` must write
**both** the `default_backend` key **and** the `backends.gitbranch` entry — a
config naming a default that is not registered is rejected by
`cmd_default_backend` (`artifact_registry.py:138-145`), so the pane must never
be able to produce one.

Widget ids carry the `_repop_counter` suffix (`_{rc}`) like every other pane, and
`on_button_pressed` matches by prefix (`btn_artifacts_save` / `btn_artifacts_revert`).

## Validation before persist

Use the **Project-Groups modal pattern** (`AssignGroupScreen._accept_new`,
L1131-1141: validate and paint the error label **before** dismissing) rather than
the save-time `yaml.safe_load` guard — an invalid branch name must never reach
disk.

The rule is **single-sourced** by shelling out to
`artifact_registry.py validate-ref`, in the `_run_projects_group` style
(`settings_app.py:2634-2650`: `subprocess.run(..., capture_output=True,
text=True, timeout=30)`, never raises, timeout/OSError → `rc=1`). **Do not
re-encode the ref regex or the reserved-branch list in Python UI code.**

## Known hazard — state it in the pane hint

`save_yaml_config` (`.aitask-scripts/lib/config_utils.py:167-172`) is
`yaml.safe_dump(..., sort_keys=False)` — it **destroys every comment** in
`project_config.yaml`, including the 37-line seeded `artifacts:` documentation
block (`seed/project_config.yaml:189-225`). This is pre-existing behavior for the
Project and Tmux tabs, but this is the first tab whose own seeded comments it
would wipe.

**Decision (do not relitigate):** accept it, matching existing behavior, and say
so in the pane's section hint. Do **not** introduce a comment-preserving YAML
round-tripper as a side effect — that is tracked as its own follow-up.

## Reference files for patterns

- `settings_app.py:2846-2966` — the tmux quartet: `_populate_tmux_tab`,
  `save_tmux_settings` (the nested-sub-map merge/drop logic), `_revert_tmux_settings`,
  `_handle_tmux_config_edit`. **The closest template.**
- `settings_app.py:2443-2581` — the flat-key Project Config pane, for `ConfigRow`
  construction, the `_repop_counter` id idiom and `_safe_id()`.
- `settings_app.py:2634-2650` — `_run_projects_group`, the never-raises
  subprocess seam to copy for the registry calls.
- `settings_app.py:1131-1141` — modal pre-dismiss validation.
- `aidocs/framework/tui_conventions.md` — mandatory before editing any Textual TUI.

## Verification steps

New `tests/test_settings_artifacts_tab.py`, combining the two shipped templates:

- **Schema/save**, from `tests/test_settings_learn_skill_guide.py`: assert the
  keys are registered with non-empty `summary`+`detail`; find the `ConfigRow` by
  `row_key` in `#artifacts_content`, set `row.raw_value`, call the real
  `app.save_project_settings()` (or `save_artifacts_settings()`), reload with
  `config_utils.load_yaml_config` and assert persistence; then blank the row and
  assert the key is **removed** and the empty `artifacts:` section dropped.
- **Subprocess seam**, from `tests/test_settings_project_groups_tab.py`: stub the
  registry call as an **instance** attribute returning canned `(0, out, "")`, and
  assert exact argv.

Named cases:
- the selector offers `gitbranch` on a project with **no** `artifacts:` block —
  the bootstrap case; this is the test that fails if `list` is used instead of
  `adapters`
- an invalid or reserved branch name produces **zero** writes (assert the config
  file is byte-unchanged, not merely that an error was shown)
- selecting `gitbranch` emits **both** `default_backend` and the
  `backends.gitbranch` entry
- the tab-switch key focuses the pane (`await pilot.press("<key>")`, assert
  `TabbedContent.active`)
- round-trip preserves unknown sibling keys under `artifacts:`

Headless instantiation follows the shipped idiom: `sys.path.insert` for
`.aitask-scripts`, `.aitask-scripts/lib`, `.aitask-scripts/settings`;
`keybinding_registry._reset_for_tests()` + `refresh_label_case()` in
setUp/tearDown; `tempfile.TemporaryDirectory()` + `os.chdir(root)` with a
hand-written `aitasks/metadata/project_config.yaml`; then
`async with app.run_test(size=(140, 45)) as pilot`.

Existing suites must stay green: `python3 tests/test_settings_learn_skill_guide.py`,
`python3 tests/test_settings_project_groups_tab.py`,
`python3 tests/test_settings_shortcuts_tab.py`,
`python3 tests/test_settings_default_profiles_unknown_keys.py`.

## Out of scope

Website documentation of the new tab is t1231_3 (including the settings
reference tables, which are already stale).

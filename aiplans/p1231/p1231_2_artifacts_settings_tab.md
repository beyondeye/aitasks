---
Task: t1231_2_artifacts_settings_tab.md
Parent Task: aitasks/t1231_configurable_git_branch_artifact_backend.md
Sibling Tasks: aitasks/t1231/t1231_1_gitbranch_artifact_backend.md, aitasks/t1231/t1231_3_artifact_documentation.md
Archived Sibling Plans: aiplans/archived/p1231/p1231_1_*.md
Base branch: main
plan_verified: []
---

# t1231_2 — Artifacts settings tab

## Context

`aitasks/metadata/project_config.yaml` in this repo has **no `artifacts:` section
at all** — `artifacts.default_backend` resolves to `local` through
`cmd_default_backend`'s absent path (`lib/artifact_registry.py:126-146`).
`seed/project_config.yaml:189-225` ships the block fully commented out.

t1231_1 adds the `gitbranch` adapter. Configuring it by hand means writing a
correct two-level nested YAML block, and getting `default_backend` and
`backends.<name>` consistent with each other. This task makes it a settings pane.

The nested-section write pattern is already established by the **Tmux tab** —
`TMUX_CONFIG_SCHEMA` + `_populate_tmux_tab` / `save_tmux_settings` /
`_revert_tmux_settings` / `_handle_tmux_config_edit`
(`.aitask-scripts/settings/settings_app.py:2846-2985`). Copy it; do not invent a
new pattern.

## Dependency on t1231_1

t1231_1 adds two `artifact_registry.py` subcommands this pane requires:

- **`adapters`** — prints `local` + `sorted(KNOWN_ADAPTERS)`: the *available*
  adapters independent of config. The existing `cmd_list`
  (`artifact_registry.py:149-154`) prints only *registered* backends, so on a
  fresh project `gitbranch` is unlistable and could never be selected to create
  its own first configuration. **The selector must use `adapters`, not `list`.**
  This is the bootstrap trap, and it has a named test below.
- **`validate-ref <name>`** — exit 0/1 + message, so the pane validates a branch
  name *before* the backend is registered.

Confirm both exist before starting (`./.aitask-scripts/lib/artifact_registry.py
--config aitasks/metadata/project_config.yaml adapters`).

## Implementation steps

### 1. Tab registration — six touch-points

All verified present in `settings_app.py`:

1. **`_TAB_SWITCH_ACTIONS`** (L172-181) — add
   `"switch_tab_artifacts": "tab_artifacts"`. Insertion order drives the
   footer-hint order, so place it where it reads sensibly among a/b/c/g/m/p/s/t.
2. **`BINDINGS`** (L1509-1516) — add
   `Binding("<key>", "switch_tab_artifacts", "Artifacts tab", show=False)`.
   **Only `k`, `o`, `z` are unbound.** Taken: `q e i r` (global), `d l`
   (shortcuts tab), `w v x` (profiles tab), `h u n y f` (project groups),
   `a b c g m p s t` (tab switches), `j` (TUI switcher via
   `TuiSwitcherMixin.SWITCHER_BINDINGS`, `lib/tui_switcher.py:1420-1422`), `?`
   (shortcut editor via `ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS`,
   `lib/shortcuts_mixin.py:79-81`). **Recommended: `k`.** Re-verify against the
   live `BINDINGS` list at implementation time — main advances between sessions.
3. **`action_switch_tab_artifacts()`** stub near L1706-1728, body
   `self._switch_to_tab("tab_artifacts")`.
4. **`compose()`** (L1573-1603) —
   `TabPane(self.label("switch_tab_artifacts", "Artifacts"), id="tab_artifacts")`
   wrapping `VerticalScroll(id="artifacts_content")`. Use `VerticalScroll` (the
   scrolling-pane form) since the pane is a list of rows, not a `DataTable`.
5. **`on_mount()`** (L1605-1613) — call `self._populate_artifacts_tab()`.
6. **Footer hint** — nothing to do. `_tab_switch_hint()` (L1730-1743) derives
   from `_TAB_SWITCH_ACTIONS` and the keybinding registry automatically.

The tab title goes through `self.label(action_id, "Artifacts")`
(`lib/shortcuts_mixin.py:136`) so a rebind is reflected on the tab.

### 2. Schema and pane

New `ARTIFACTS_CONFIG_SCHEMA` at module level, beside `TMUX_CONFIG_SCHEMA`
(L183+), with per-key `summary` and `detail` (both non-empty — `test_settings_learn_skill_guide.py`'s
schema test asserts this shape for project-config keys):

- **`default_backend`** — a `CycleField`, options from
  `artifact_registry.py adapters`. Default `local`.
- **`backends.gitbranch.branch`** — a `ConfigRow`, default `aitask-artifacts`.

`_populate_artifacts_tab()` mirrors `_populate_tmux_tab`: bump `_repop_counter`,
mount a `section-header` Label, a `section-hint` Label (see the hazard note
below), the rows with `_{rc}`-suffixed ids, a `Horizontal(classes="tab-buttons")`
with `btn_artifacts_save` / `btn_artifacts_revert`, and a trailing hint line
including `self._tab_switch_hint()`.

`save_artifacts_settings()` mirrors `save_tmux_settings` (L2904-2960):

```python
data = dict(self.config_mgr.project_config)
if artifacts_data:
    existing = dict(data.get("artifacts") or {})
    existing.update(artifacts_data)      # nested merge, not replace
    data["artifacts"] = existing
else:
    # pop the schema keys; drop the section if it becomes empty
...
self.config_mgr.save_project_settings(data)
self.config_mgr.load_all()
self._populate_artifacts_tab()
```

Seeding from `dict(self.config_mgr.project_config)` is what preserves unknown
sibling keys — the property `test_settings_default_profiles_unknown_keys.py`
pins for `default_profiles` and which this pane must preserve for `artifacts:`.

`_revert_artifacts_settings()` and `_handle_artifacts_config_edit()` mirror their
tmux counterparts (L2963-2985): the edit callback writes `row.raw_value` in the
DOM and notifies "press Save to persist" — **nothing hits disk until Save**.

`on_button_pressed` (L3442+) matches by prefix because of the `_{rc}` suffix:
`btn_id.startswith("btn_artifacts_save")` / `..._revert`.

### 3. Self-consistency invariant

Selecting `gitbranch` as `default_backend` must write **both** the
`default_backend` key **and** the `backends.gitbranch` entry. A config naming a
default that is not registered is rejected by `cmd_default_backend`
(`artifact_registry.py:138-145` — "is not registered under artifacts.backends"),
so the pane must be structurally incapable of producing one. Conversely,
clearing the branch row while `gitbranch` is the default must be refused, not
silently saved.

### 4. Validation before persist

Use the **Project-Groups modal pattern** — `AssignGroupScreen._accept_new`
(L1131-1141) validates and paints `#assign_group_error` **before dismissing**, so
an invalid value never reaches the subprocess. Do the same here: an invalid
branch name must never reach disk. This is stronger than the Project tab's
save-time `yaml.safe_load` guard (L2569-2573), which aborts the whole save after
the fact.

The rule is **single-sourced** by shelling out to
`artifact_registry.py validate-ref`, in the `_run_projects_group` style
(L2634-2650):

```python
subprocess.run([...], capture_output=True, text=True, timeout=30)
# never raises; timeout/OSError -> rc = 1
```

**Do not re-encode the ref regex or the reserved-branch list in Python UI code.**
Two copies of that rule will drift, and the reserved list is a data-safety guard
(it is what stops the blob store pointing at `main`).

### 5. Comment-destruction hazard — state it, do not fix it

`save_yaml_config` (`lib/config_utils.py:167-172`) is
`yaml.safe_dump(..., sort_keys=False)`. It round-trips **values only** — every
`#` comment in `project_config.yaml` is destroyed on write, including the 37-line
seeded `artifacts:` documentation block.

This is long-standing behavior for the Project and Tmux tabs, but this is the
first tab whose *own* seeded comments it would wipe.

**Decision (settled at t1231 planning — do not relitigate):** accept it, matching
existing behavior, and say so plainly in the pane's `section-hint`. Do **not**
introduce a comment-preserving YAML round-tripper as a side effect of this task —
that is **t1260**, which owns the shared `save_yaml_config` seam and its full
call-site blast radius.

## Reference files for patterns

- `settings_app.py:2846-2985` — the tmux quartet. **The closest template**;
  copy its nested merge/drop logic verbatim in shape.
- `settings_app.py:2443-2581` — the flat-key Project Config pane, for `ConfigRow`
  construction, the `_repop_counter` id idiom, `_safe_id()` (L317), and the
  empty-value → `data.pop(key)` "unset ⇒ default" contract.
- `settings_app.py:2634-2650` — `_run_projects_group`, the never-raises
  subprocess seam to copy for the registry calls.
- `settings_app.py:1131-1141` — modal pre-dismiss validation.
- `settings_app.py:1524-1571` — `check_action`, if any tab-scoped bare-key
  action is added (not required for a plain config pane).
- `aidocs/framework/tui_conventions.md` — **mandatory** before editing any
  Textual TUI under `.aitask-scripts/`.

## Verification

New `tests/test_settings_artifacts_tab.py`, combining the two shipped templates.

Headless instantiation follows the shipped idiom exactly: `sys.path.insert` for
`.aitask-scripts`, `.aitask-scripts/lib`, `.aitask-scripts/settings`;
`keybinding_registry._reset_for_tests()` + `refresh_label_case()` in
`setUp`/`tearDown`; `tempfile.TemporaryDirectory()` + `os.chdir(root)` with a
hand-written `aitasks/metadata/project_config.yaml`; then

```python
async def runner():
    app = SettingsApp()
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        ...
asyncio.run(runner())
```

Named cases:

1. **Schema shape** — both keys registered with non-empty `summary` + `detail`
   (pattern: `test_settings_learn_skill_guide.py::SchemaTests`).
2. **Save/clear round-trip** — find the `ConfigRow` by `row_key` in
   `#artifacts_content`, set `row.raw_value`, call the real save method, reload
   with `config_utils.load_yaml_config`, assert persistence; then blank the row
   and assert the key is **removed** and an emptied `artifacts:` section dropped
   (pattern: `test_settings_learn_skill_guide.py::SavePathTests`).
3. **Bootstrap case** — on a project with **no** `artifacts:` block, the selector
   offers `gitbranch`. *This is the test that fails if `list` is used instead of
   `adapters`.*
4. **Invalid / reserved branch name produces zero writes** — assert the config
   file is **byte-unchanged** (not merely that an error was displayed), and that
   the validate subprocess was called with the expected argv. Cover at least one
   malformed name and one reserved name (`main`).
5. **Self-consistency** — selecting `gitbranch` emits **both**
   `default_backend: gitbranch` and the `backends.gitbranch.branch` entry.
6. **Tab switch** — `await pilot.press("<key>")` then assert
   `app.query_one(TabbedContent).active == "tab_artifacts"`.
7. **Unknown-sibling preservation** — an unrelated key under `artifacts:`
   survives a save, with a tripwire asserting the probe key really is unknown to
   the schema (pattern: `test_settings_default_profiles_unknown_keys.py::NegativeControlTests`).

Subprocess seam stubbed as an **instance** attribute returning canned
`(0, out, "")`, asserting exact argv tuples — pattern:
`tests/test_settings_project_groups_tab.py`.

Regression suites that must stay green:

```bash
python3 tests/test_settings_learn_skill_guide.py
python3 tests/test_settings_project_groups_tab.py
python3 tests/test_settings_shortcuts_tab.py
python3 tests/test_settings_default_profiles_unknown_keys.py
python3 tests/test_settings_brainstorm_descriptions.py
```

Manual: `ait settings`, press the new key, set `default_backend: gitbranch`,
save, and confirm `aitasks/metadata/project_config.yaml` gained a well-formed
`artifacts:` block that `./.aitask-scripts/lib/artifact_registry.py --config
aitasks/metadata/project_config.yaml default-backend` accepts.

## Out of scope

Website documentation of the new tab — including the settings reference tables,
which are **already stale** (they omit the shipped Shortcuts tab) — is t1231_3.
Comment preservation in `save_yaml_config` is t1260.

## Post-implementation

Per `task-workflow` Step 9 — merge approval, `ait gates run 1231_2`, archival.

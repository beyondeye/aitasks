---
Task: t1231_2_artifacts_settings_tab.md
Parent Task: aitasks/t1231_configurable_git_branch_artifact_backend.md
Sibling Tasks: aitasks/t1231/t1231_1_gitbranch_artifact_backend.md, aitasks/t1231/t1231_3_artifact_documentation.md
Archived Sibling Plans: aiplans/archived/p1231/p1231_1_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-19 11:43
---

# t1231_2 — Artifacts settings tab

## Context

`aitasks/metadata/project_config.yaml` has **no `artifacts:` section** — the
default backend resolves to `local` through `cmd_default_backend`'s absent path
(`.aitask-scripts/lib/artifact_registry.py:172-192`). t1231_1 (landed,
3d9e4371d) added the `gitbranch` adapter plus two registry verbs this pane
consumes. Configuring it today means hand-writing a nested two-level YAML block
whose `default_backend` and `backends.<name>` must agree. This task adds an
**Artifacts** tab to `ait settings` that edits that block.

### Verification findings (2026-10-19, against HEAD f4f3885f9)

The original plan's line numbers had drifted (settings_app.py is now 4810
lines). Corrected anchors and facts used below:

- Registry verbs confirmed in `artifact_registry.py`: `adapters` (L203-211)
  prints `local`, `dir`, `gitbranch` **independent of config**; `validate-ref`
  (L214-218) exits 0, or 1 with the reason on stderr; the rule lives once in
  `check_ref_name` (L103-129, reserved: main, master, aitask-data, aitask-locks,
  aitask-ids + HEAD). **NB:** `main()` loads the config before dispatching, so
  even `adapters` fails on a malformed config file → the pane needs a fallback.
  The script is **not executable** (no +x) → invoke via `sys.executable`.
- **`adapters` also offers `dir`** (needs `backends.dir.path`), which the
  original plan never addressed. The pane does not grow a `dir.path` row;
  instead the save path asks the registry itself whether the candidate config is
  acceptable — `default-backend` **and** `backend-env <default>` (step 4), since
  `default-backend` alone passes `dir` with an empty or relative path (verified)
  — so selecting `dir` saves only when a valid `backends.dir.path` is already
  configured (hand-written YAML, preserved as an unknown sibling) and is refused
  with the registry's own message otherwise.
- The project loader accepts non-mapping nested values (`artifacts: oops`, …),
  and `dict("oops")` raises `ValueError` → the save path guards each nesting
  level before converting (step 4).
- Tmux quartet is now `settings_app.py:3632-3786`, and its save path goes through
  `_may_save("project")` / `_refresh_after_save("project", …)` /
  `_refresh_for_revert(...)` (L4644-4682) — not `load_all()` as the old plan
  said. `ConfigManager.save_project_settings` (L916) also commits the file
  (`_commit`), so the new pane inherits commit-on-save for free.
- `_TAB_SWITCH_ACTIONS` L199-208; `BINDINGS` L1977-2022; `compose()` L2102;
  `on_mount()` L2134; `action_switch_tab_tmux` L2256; Enter-to-edit dispatch for
  `tmux_cfg_` rows L2391-2399; `on_cycle_field_changed` L4220; `on_button_pressed`
  L4243 (tmux arms L4277-4280); `_reload_all_configs` L4684 (repopulates every
  tab — must include the new one); `_run_projects_group` L3438 (subprocess seam
  template); `AssignGroupScreen._accept_new` L1562 (pre-dismiss validation).
- Free keys: **`o` is now taken** (`agent_switch_superseded`). Unbound: `k`, `z`.
  → use **`k`**. (`j` TUI switcher, `?` shortcut editor.)
- `tests/test_settings_shortcuts_tab.py` pins the tab inventory: `_TAB_ACTIONS`
  (L387-396), the hint literal `"a/b/c/g/m/p/s/t: switch tabs"` (L424, L431) and
  the tab-label dict (L497-506). These must be updated in the same change.
- `CycleField` / `ConfigRow` / `EditStringScreen` live in
  `.aitask-scripts/lib/profile_editor.py` (L439/L531/L575). `EditStringScreen`
  has no validator hook → a small dedicated modal is needed for pre-dismiss
  validation.
- Inbox note from t1231_1 (advisory, acknowledged): changing the branch once a
  store exists makes every gitbranch op refuse until
  `ait artifact gitbranch-migrate --from <old> --to <new>`. Detecting a store
  would mean reading the data branch from the TUI — out of scope (minimal +
  advisory): the pane warns on any branch change instead (step 6).

## Implementation steps

All in `.aitask-scripts/settings/settings_app.py` unless noted.

### 1. Tab registration (six touch-points)

1. `_TAB_SWITCH_ACTIONS` — insert `"switch_tab_artifacts": "tab_artifacts"`
   right after `switch_tab_project_groups`, so the hint reads
   `a/b/c/g/k/m/p/s/t`. Update the comment above it (it lists the keys).
2. `BINDINGS` — `Binding("k", "switch_tab_artifacts", "Artifacts tab", show=False)`
   beside the other tab switches.
3. `action_switch_tab_artifacts()` → `self._switch_to_tab("tab_artifacts")`,
   next to `action_switch_tab_tmux`.
4. `compose()` — after the Tmux pane:
   `with TabPane(self.label("switch_tab_artifacts", "Artifacts"), id="tab_artifacts"): yield VerticalScroll(id="artifacts_content")`.
5. `on_mount()` and `_reload_all_configs()` — call `self._populate_artifacts_tab()`
   right after `_populate_tmux_tab()`.
6. Footer hint — nothing: `_tab_switch_hint()` derives from `_TAB_SWITCH_ACTIONS`.

### 2. Schema + registry seam

Module level, beside `TMUX_CONFIG_SCHEMA`:

```python
ARTIFACT_REGISTRY = _SETTINGS_DIR.parent / "lib" / "artifact_registry.py"
ARTIFACTS_GITBRANCH_DEFAULT_BRANCH = "aitask-artifacts"

ARTIFACTS_CONFIG_SCHEMA: dict[str, dict[str, str]] = {
    "default_backend": {"summary": ..., "detail": ..., "type": "enum", "default": "local"},
    "backends.gitbranch.branch": {"summary": ..., "detail": ..., "type": "string",
                                  "default": ARTIFACTS_GITBRANCH_DEFAULT_BRANCH},
}
```

(`_SETTINGS_DIR` is defined after `_safe_id`, so place `ARTIFACT_REGISTRY` after
it.) Both keys get non-empty `summary` + `detail`.

Seam method (copy of `_run_projects_group`'s never-raises shape):

```python
def _run_artifact_registry(self, *args: str, config: str | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            [sys.executable, str(ARTIFACT_REGISTRY), "--config",
             config or str(PROJECT_CONFIG), *args],
            capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)
```

Tests replace it as an **instance** attribute.

Helpers:
- `_artifact_adapters()` → `adapters` output lines; on rc≠0 fall back to
  `["local"]` plus the currently configured default (so the CycleField never
  silently rewrites it), and notify the stderr as an error.
- `_artifact_ref_error(branch) -> str | None` → `validate-ref <branch>`; rc 0 →
  `None`, else the stripped stderr (or a generic message when empty). The ref
  rule is **never** re-encoded in Python.

### 3. Pane (`_populate_artifacts_tab`)

Mirror `_populate_tmux_tab`: clear `#artifacts_content`, bump `_repop_counter`,
store `self._artifacts_tab_rc`, then mount:

- `section-header` "Artifact Storage"; `section-hint` explaining that this edits
  the `artifacts:` block of `aitasks/metadata/project_config.yaml`, that the
  gitbranch store is created lazily on first write (or `ait artifact init-store
  gitbranch`), and — **stated plainly** — that saving rewrites
  project_config.yaml **without its comments** (including the seeded
  `artifacts:` documentation block), as the Project and Tmux tabs already do.
- `CycleField("default_backend", adapters, current, field_key="default_backend", id=f"artifacts_cycle_default_backend_{rc}")`.
  `current` = configured value or `local`; if the configured value is not in
  the adapter list, prepend it so the field shows the truth (save then lets the
  registry judge it).
- `ConfigRow("gitbranch branch", display, row_key="backends.gitbranch.branch", id=f"artifacts_cfg_gitbranch_branch_{rc}", raw_value=<configured or "">)`;
  display `(not set)` when empty.
- A summary `section-hint` under each, a warning hint line about
  `ait artifact gitbranch-migrate --from <old> --to <new>` when changing the
  branch of an existing store, `Horizontal(classes="tab-buttons")` with
  `btn_artifacts_save_{rc}` / `btn_artifacts_revert_{rc}`, and the
  `Enter: edit | ←→: cycle | ↑↓: navigate | {self._tab_switch_hint()}` line.

Read the current block through `_artifacts_sections()` (step 4). On a
malformed section (present but not a mapping) the pane still mounts its rows
with defaults, plus a red `section-hint` naming the malformed path and saying
Save is refused until the YAML is fixed by hand — display tolerates, save
refuses.

### 4. Save (`save_artifacts_settings`) — validate everything, then write once

```text
if not self._may_save("project"): return
default = cycle.current_value
branch  = (row.raw_value or "")            # raw, not stripped — validate-ref
                                            # judges the raw string as activation does
shape guard (before ANY dict() conversion):
  artifacts_raw = data.get("artifacts");                   None -> {}; not dict -> refuse
  backends_raw  = artifacts.get("backends");               None -> {}; not dict -> refuse
  gb_raw        = backends.get("gitbranch");               None -> {}; not dict -> refuse
  refuse = notify error naming the dotted path and its type
  ("artifacts.backends is a str, not a mapping — fix project_config.yaml by hand,
  then press r to reload"), return. Never coerce `x or {}` — a malformed
  section must not be silently replaced (and dict("oops") raises ValueError).
  Implemented as one helper `_artifacts_sections(config) -> (artifacts, backends,
  gitbranch) | str error`, shared with the pane's read path (step 3), which shows
  the same error as a red section-hint instead of the rows' values.
if branch:   err = _artifact_ref_error(branch) -> notify error, return   (zero writes)
if default == "gitbranch" and not branch -> notify "gitbranch needs a branch", return
build candidate (copies of the guarded mappings — unknown siblings preserved):
  data      = dict(project_config)
  artifacts = dict(artifacts_raw); backends = dict(backends_raw); gb = dict(gb_raw)
  branch ? gb["branch"] = branch : gb.pop("branch")
  gb ? backends["gitbranch"] = gb : backends.pop("gitbranch")
  backends ? artifacts["backends"] = backends : artifacts.pop("backends")
  default != "local" ? artifacts["default_backend"] = default : artifacts.pop("default_backend")
  artifacts ? data["artifacts"] = artifacts : data.pop("artifacts")
registry acceptance check — yaml.safe_dump(candidate) into a NamedTemporaryFile
  (deleted in `finally`), then against config=<tmp>:
  1. `default-backend`          — default is registered and has an adapter
  2. `backend-env <default>`    — when default != local: its REQUIRED settings
                                   are present and valid (dir.path non-empty and
                                   absolute; gitbranch.branch a valid ref).
                                   `default-backend` alone does NOT check these:
                                   verified, `dir` with `{}` or `path: relative/store`
                                   passes it (rc 0) while `backend-env dir` exits 1.
  (No check on a registered-but-not-default backend: a non-empty branch is
  already judged by `validate-ref` above, and a cleared branch leaving
  unknown keys in `backends.gitbranch` — e.g. `extra: keep-me` — is a legal,
  inactive entry. Running `backend-env gitbranch` on it would reject the
  clear-and-preserve case, verified against the real registry.)
  any rc != 0 -> notify that call's stderr, return (zero writes). Every rule —
  registration, adapter existence, required keys, path/ref shape — stays in the
  registry; the pane re-encodes none of it.
if old branch (from loaded config) is non-empty and != new branch:
  notify warning naming `ait artifact gitbranch-migrate --from <old> --to <new>`
self.config_mgr.save_project_settings(data)
if self._refresh_after_save("project", "Artifact settings saved"):
    self._populate_artifacts_tab(); notify
```

Every refusal returns **before** `save_project_settings`, so an invalid config
never reaches disk. `local` → the key is dropped ("unset ⇒ default").

### 5. Edit flow + pre-dismiss validation

- New `EditArtifactBranchScreen(GuardedModalScreen)` near `AssignGroupScreen`:
  `Input` + `Label(id="edit_branch_error")` + Save/Cancel. Takes `key`,
  `current`, and a `validate: Callable[[str], str | None]`. On submit: empty →
  dismiss (clearing is legal; the save rule handles the gitbranch-default case);
  else `why = validate(value)`; if `why` paint it red in `#edit_branch_error`
  and **do not dismiss**; else dismiss `{"key", "value"}`. The app passes
  `self._artifact_ref_error`, so the single registry rule is used here too.
- `on_key` Enter dispatch: an `artifacts_cfg_` arm beside the `tmux_cfg_` one,
  storing `self._editing_artifacts_row_id` and pushing the modal with callback
  `_handle_artifacts_config_edit` (mirrors `_handle_tmux_config_edit`: DOM only,
  "press Save to persist").
- `on_cycle_field_changed`: before the existing early-return, if the field id
  starts with `artifacts_cycle_` and the value is `gitbranch` while the branch
  row is empty, prefill the row with `ARTIFACTS_GITBRANCH_DEFAULT_BRANCH` (DOM
  only) and notify — so selecting gitbranch on a fresh project saves **both**
  keys. Then return.
- `_revert_artifacts_settings()` = `_refresh_for_revert(reload_project_config)`
  + repopulate + notify.
- `on_button_pressed`: `btn_artifacts_save` / `btn_artifacts_revert` prefix arms.

### 6. Shortcuts test inventory (`tests/test_settings_shortcuts_tab.py`)

Add `"switch_tab_artifacts": ("k", "tab_artifacts")` to `_TAB_ACTIONS`, update
both hint literals to `a/b/c/g/k/m/p/s/t` / `1/b/c/g/k/m/p/s/t`, and add
`tab_artifacts` to the tab-label dict with whatever label `self.label()` renders
for `k` on "Artifacts" (checked by running the test, not guessed).

## Verification

New `tests/test_settings_artifacts_tab.py` (unittest, headless, idiom of
`test_settings_project_groups_tab.py`: sys.path inserts,
`keybinding_registry._reset_for_tests()` + `refresh_label_case()`, temp dir +
chdir, hand-written `aitasks/metadata/project_config.yaml` + `userconfig.yaml`,
`app.run_test(size=(140, 45))`). The registry seam is stubbed as an instance
attribute recording `(config, args)` with canned results; one test runs the
**real** registry (no stub) for the bootstrap case so the `adapters` wiring is
proven end-to-end. Cases:

1. **Schema shape** — both keys present with non-empty `summary` + `detail`.
2. **Bootstrap** — config with no `artifacts:` block: the default_backend
   CycleField offers `gitbranch` (real registry). Fails if `list` is used.
3. **Self-consistency** — cycle to `gitbranch` on a fresh config → row is
   prefilled → save → file has `default_backend: gitbranch` **and**
   `backends.gitbranch.branch: aitask-artifacts`; real `default-backend` accepts it.
4. **Invalid / reserved branch → zero writes** — set row raw_value to
   `"bad name"` and to `main`, save: config file **byte-identical**, stub saw
   `("validate-ref", <value>)`, no `save_project_settings` call. Also the modal:
   submitting `main` keeps `EditArtifactBranchScreen` open with the error label
   painted.
5. **gitbranch default with empty branch refused** — zero writes.
6. **`dir` default validated through `backend-env`** (real registry) — select
   `dir` with: no `backends.dir`; `backends.dir: {}`; `backends.dir.path:
   relative/store` → each **zero writes** (byte-identical file) with the
   registry's message notified; with `backends.dir.path: /abs/store` it saves.
   The stubbed variant asserts the call sequence `default-backend` then
   `backend-env dir` against the temp config, and that the temp file is gone
   afterwards.
6b. **Malformed nested sections refused** — `artifacts: oops`,
   `artifacts: {backends: oops}`, `artifacts: {backends: {gitbranch: oops}}`:
   the tab mounts (no crash) showing the error hint, and Save is refused with an
   error naming the dotted path — file byte-identical, no registry call made.
7. **Clear round-trip** — set `local` + blank branch: `default_backend`,
   `backends.gitbranch` and the emptied `artifacts:` section are dropped.
8. **Unknown siblings preserved** — `artifacts.extra_probe`,
   `artifacts.backends.dir`, `artifacts.backends.gitbranch.extra` survive a save,
   with a tripwire asserting the probe keys are not in `ARTIFACTS_CONFIG_SCHEMA`.
8b. **Clear + preserve combined** (real registry) — start from
   `default_backend: gitbranch`, `backends.gitbranch: {branch: aitask-artifacts,
   extra: keep-me}`; select `local`, blank the branch, save → the save
   **succeeds**, `default_backend` and `branch` are gone, and
   `backends.gitbranch.extra: keep-me` survives.
9. **Tab switch** — `await pilot.press("k")` → `TabbedContent.active == "tab_artifacts"`.
10. **Branch-change warning** — changing an existing branch notifies the
    gitbranch-migrate command (capture via `app.notify` instance stub).

Commands:

```bash
python3 tests/test_settings_artifacts_tab.py
python3 tests/test_settings_shortcuts_tab.py
python3 tests/test_settings_learn_skill_guide.py
python3 tests/test_settings_project_groups_tab.py
python3 tests/test_settings_default_profiles_unknown_keys.py
python3 tests/test_settings_brainstorm_descriptions.py
python3 tests/test_settings_reload_all.py
python3 tests/test_settings_commit_on_save.py
```

Manual (optional): `ait settings` → `k` → cycle to gitbranch → Save → 
`python3 .aitask-scripts/lib/artifact_registry.py --config aitasks/metadata/project_config.yaml default-backend`
prints `gitbranch`. (Not done against this repo's real config without asking —
saving strips its comments.)

## Out of scope

Website docs for the tab (t1231_3). Comment-preserving YAML writes (t1260).
Detecting an existing gitbranch store from the TUI (the warning is advisory).

## Step 9 (Post-Implementation)

Per task-workflow Step 9: review, commit, `risk_evaluated` gate, archival.

## Risk

### Code-health risk: low
- `settings_app.py` is large and central; the change adds one tab plus arms in shared dispatchers (`on_key`, `on_cycle_field_changed`, `on_button_pressed`, `_reload_all_configs`) — a missed arm silently breaks edit/save. Contained by prefix-matched ids and the per-case tests · severity: low · → mitigation: covered in-plan (tests 3-9)
- Saving from this tab destroys every comment in `project_config.yaml`, incl. the seeded `artifacts:` docs block · severity: medium · → mitigation: t1260 (existing follow-up; decision settled at t1231 planning, stated in the pane hint)

### Goal-achievement risk: low
- Changing the branch after a store exists breaks gitbranch ops until migrated; the pane warns but cannot detect a store · severity: low · → mitigation: none — the ops fail closed with the migrate message (t1231_1), and the warning names the command

## Post-Review Changes

### Change Request 1 (2026-10-19 12:40)
- **Requested by user:** two verified defects:
  1. `default_backend: "[/bold]"` crashed the tab with `MarkupError` —
     `CycleField.render` interpolated options (and the label) into markup, and
     the pane deliberately shows an unrecognised configured value as-is;
  2. a YAML branch containing a NUL byte crashed Save — `subprocess.run`
     raises `ValueError: embedded null byte`, which `_run_artifact_registry`
     (documented as never-raises) did not catch.
- **Changes made:**
  1. `lib/profile_editor.py` `CycleField.render` now `escape()`s the label and
     every option (raw values unchanged for selection/registry; rendered width
     still `len(opt)`, which `_option_index_at` relies on). Fixed at the shared
     widget rather than per caller: no caller passes markup there, and
     `compose_profile_fields` has the same inserted-config-value shape.
  2. `_run_artifact_registry` also catches `ValueError` → `rc=1` with
     "cannot run the artifact registry: …"; no registry rule is re-encoded.
  3. Traced the same untrusted text into the toasts: refusal notifications
     quote the rejected value (registry `%r`) and old branch names come from
     the YAML, so every interpolated notify text in the tab is now escaped.
     Probed Textual 8.2.7: a toast tolerates broken markup (no crash), so this
     is about literal display — unescaped, `[b]x[/b]` renders as a bold "x".
- **Tests added** (`tests/test_settings_artifacts_tab.py`, now 17): the
  notify spy now passes through to the real `notify`;
  `HostileValueTests` — `[/bold]` default renders (raw value kept) and is
  refused via the real Save button with zero writes; the refusal toast shows
  `[b]x[/b]` literally (checked through `Content.from_markup(...).plain`); a
  YAML `"bad\0branch"` is refused through the Save button without crashing.
  **Red proof** (isolated copies): un-escaping `CycleField` → MarkupError;
  un-escaping the notify → literal-toast test fails; dropping `ValueError` →
  `ValueError: embedded null byte`.
- **Regression:** every suite touching `CycleField` / `profile_editor` /
  `agent_command_screen` / the chatlink wizard / `settings_app` (43 files,
  1067 tests, pytest `-n 4 --dist loadfile`) passes.
- **Files affected:** `.aitask-scripts/lib/profile_editor.py`,
  `.aitask-scripts/settings/settings_app.py`,
  `tests/test_settings_artifacts_tab.py`

## Final Implementation Notes
- **Actual work done:** An **Artifacts** tab in `ait settings` (key `k`,
  between Project Groups and Models in the hint order `a/b/c/g/k/m/p/s/t`)
  editing `artifacts.default_backend` (a `CycleField` fed by
  `artifact_registry.py adapters`) and `artifacts.backends.gitbranch.branch`
  (a `ConfigRow` edited through the new `EditArtifactBranchScreen`, which runs
  `validate-ref` before it dismisses). Save (`save_artifacts_settings`) guards
  the three nesting levels, validates a non-empty branch, refuses a gitbranch
  default with no branch, builds the candidate from copies of the existing
  sections (unknown keys survive, emptied sections are dropped), then asks the
  registry about a temp copy of the candidate — `default-backend`, plus
  `backend-env <default>` for a non-local default — and only then calls
  `ConfigManager.save_project_settings` (which commits). Selecting gitbranch
  with an empty branch prefills `aitask-artifacts` in the pane. A branch change
  notifies the exact `ait artifact gitbranch-migrate --from … --to …` command.
  The section hint states that saving drops the file's comments.
- **Deviations from plan:** none beyond the plan's own verification findings
  (key `k` because `o` is taken; `dir` handled through the registry check) and
  the two plan-review rounds (`backend-env <default>`; shape guards; no check on
  a registered-but-inactive gitbranch entry, which would break
  clear-and-preserve). Post-review: `CycleField.render` escapes label/options
  (shared fix in `lib/profile_editor.py`), `_run_artifact_registry` catches
  `ValueError`, notify text is escaped — see Change Request 1.
- **Issues encountered:** the registry script has no +x bit, so the seam runs
  it with `sys.executable`; the test fixture is not a git repo, so every save
  in the tests also raises the expected "saved but NOT committed" toast (tests
  assert on "Not saved" refusals, not on the absence of any error). Textual
  8.2.7 toasts tolerate broken markup, so the toast escape is pinned by a
  literal-display test (`Content.from_markup(...).plain`), not a crash test.
- **Key decisions:** every rule stays in `artifact_registry.py` (ref shape,
  reserved names, registration, required backend keys, absolute dir path); the
  pane re-encodes none of it and validates the whole candidate through the
  registry against a temp file. No `dir.path` row — a `dir` default saves only
  when a valid `backends.dir.path` already exists in the YAML. No store
  detection for the branch-change warning (advisory, always shown on change).
  `local` as default is written as "key absent" (unset ⇒ default).
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t1231_3 (docs): the tab is **Artifacts**, key `k`; it edits
    `artifacts.default_backend` (options = `ait`'s available adapters: `local`,
    `dir`, `gitbranch`) and `artifacts.backends.gitbranch.branch`. A `dir`
    backend is not configurable in the tab — its `path` must be hand-written
    (absolute) before `dir` can be saved as the default. Save rewrites
    `project_config.yaml` without comments (t1260 owns comment preservation).
    The settings reference tables must now list nine tabs, incl. the
    already-missing Shortcuts tab.
  - t1231_4 (manual verification): exercise in a scratch project, not this
    repo — a save strips the real `project_config.yaml`'s comments.
  - Pattern: to validate a config edit against a CLI authority before
    persisting, dump the candidate to a temp file and run the authority's own
    verbs on it (`_artifacts_candidate_error`), rather than re-encoding rules.
  - `CycleField` (lib/profile_editor.py) now renders label/options literally;
    a caller that wanted markup there would need a different widget.

---
Task: t1945_validate_settings_config_layer_value_types.md
Base branch: main
Output branch: main
---

# t1945: Validate Settings config layer value shapes

## Context

t1938 made `ConfigManager.load_all()` all-or-nothing. Each JSON layer is read
once by `_read_json_layer(path)`, which rejects a non-object root with
`ConfigReadError(path, …)`. `SettingsApp._reload_all_configs()` catches
`ConfigReadError`, names the file, and keeps the loaded state.

A well-formed layer with a wrong-typed value still gets through. With
`codeagent_config.json` = `{"defaults": null}`, `deep_merge` replaces the default
`{}` with `None` and `load_all` swaps the in-memory state. The next
`_populate_agent_tab` then raises `AttributeError: 'NoneType' object has no
attribute 'keys'` (`settings_app.py:2424-2425` / `2483-2484`), outside the reload
`try`, and the app exits. Two more paths reach the same state:

- `ConfigManager.reload_codeagent()`, used by the superseded-model switch, merges
  through `load_layered_config` and does not even check that the root is an
  object.
- The nine direct `load_all()` callers in the save/revert handlers have **no**
  error handling (see step 4). Today an unrelated mistyped file passes
  `load_all` silently. For example, board revert completes with `{"defaults":
  null}` on disk, because only the board tab is repopulated. Once `load_all`
  validates shapes, that same state raises `ConfigReadError` out of
  `on_button_pressed`. Stricter validation would therefore **introduce** a crash
  on these paths, so they are in scope. This was confirmed by a review probe.

Goal: reject a layer whose container-typed keys have the wrong shape, per layer
and before assignment, through `ConfigReadError` naming the offending file.
Every path that re-reads configs must report that error instead of raising. A
save/revert must not be blocked by an unrelated file, and must say accurately
whether the write already landed.

## Which keys are validated (readers' actual dependencies)

Only keys a Settings reader dereferences as a container. Rejecting a shape no
reader depends on would turn a working boot into a refusal.

| file | key | must be | reader that breaks otherwise |
|---|---|---|---|
| codeagent layers | `defaults` | object | `.get(...)`/`.keys()` at 2213, 2424, 2483 |
| board layers | `columns` | array of objects | `for col in columns: col.get(...)` at 3025 |
| board layers | `settings` | object | `settings.get(...)` at 3034; `merged["settings"][…] =` in `save_board_settings` |

These are deliberately **not** validated:
- `column_order` (the task suggested it): Settings never reads it, and the board
  reader (`lib/board_columns.py:451`) already degrades a non-list to `[]`.
- Values inside `defaults`: every reader `str()`s them.
- `project_config.yaml` values: `load_yaml_config` already maps a non-mapping
  root to `{}`, and its readers guard (`default_profiles` and `tmux` check
  `isinstance`; the others go through `_format_yaml_value`).

A key a layer omits is fine. Per-layer validation is enough for the merged
result: `deep_merge` takes each key from the last layer that sets it (dicts merge
recursively into a dict), else from the defaults, which have the right shapes.

## Implementation steps

### 1. `.aitask-scripts/settings/settings_app.py`: shape check in the layer reader

Next to `_read_json_layer` (~line 561):

```python
#: Keys a Settings reader indexes as a container, per JSON config: a layer may
#: omit one, but one it sets must have this shape (t1945). (container, item).
_CODEAGENT_LAYER_SHAPE = {"defaults": (dict, None)}
_BOARD_LAYER_SHAPE = {"columns": (list, dict), "settings": (dict, None)}

_JSON_TYPE_NAMES = {dict: "object", list: "array", str: "string",
                    bool: "boolean", int: "number", float: "number",
                    type(None): "null"}


def _json_type(value) -> str:
    return _JSON_TYPE_NAMES.get(type(value), type(value).__name__)


def _check_layer_shape(path, data: dict, shape: dict) -> None:
    """Raise ConfigReadError(path) when a key a reader depends on is mistyped."""
    for key, (kind, item_kind) in shape.items():
        if key not in data:
            continue
        value = data[key]
        if not isinstance(value, kind):
            raise ConfigReadError(path, f"'{key}' must be a JSON "
                                  f"{_JSON_TYPE_NAMES[kind]}, got {_json_type(value)}")
        if item_kind is not None:
            for i, item in enumerate(value):
                if not isinstance(item, item_kind):
                    raise ConfigReadError(path, f"'{key}[{i}]' must be a JSON "
                                          f"{_JSON_TYPE_NAMES[item_kind]}, got {_json_type(item)}")
```

`_read_json_layer(path, shape=None)` calls `_check_layer_shape` after its
object-root check when `shape` is given. The existing root message stays as it
is, because a test asserts "JSON object".

### 2. Per-family readers; `load_all` composes them

Module-level, each one raising `ConfigReadError` and assigning nothing:

```python
def _read_codeagent_layers():
    """(merged, project, local) for codeagent_config, each layer validated."""
    project = _read_json_layer(CODEAGENT_CONFIG, _CODEAGENT_LAYER_SHAPE)
    local = _read_json_layer(local_path_for(str(CODEAGENT_CONFIG)),
                             _CODEAGENT_LAYER_SHAPE)
    return _merge_layers({"defaults": {}}, project, local), project, local

def _read_board_layers():      # same shape, board defaults + _BOARD_LAYER_SHAPE
def _read_project_config():    # _read_config(PROJECT_CONFIG, lambda: load_yaml_config(PROJECT_CONFIG))
```

`load_all` calls all three, then reads the models exactly as today, then assigns
everything. It stays all-or-nothing and its body shrinks. Its docstring changes
"unreadable file" to "unreadable or malformed file (bad JSON/YAML, a non-object
root, or a mistyped key a reader depends on)".

New/changed `ConfigManager` methods, each assigning only its own family and only
after its reads succeed:
- `reload_codeagent()` → `_read_codeagent_layers()`. It now raises
  `ConfigReadError` (a `ValueError`) naming the layer, so `_switch_superseded`'s
  `(OSError, ValueError)` handlers are unchanged. It also reads each file once
  and rejects a non-object root, matching `load_all`. Update its docstring.
- `reload_board()` → `_read_board_layers()` (new).
- `reload_project_config()` → `_read_project_config()` (new).

### 2b. Refresh latch: no write builds on memory that is behind its own save

After a save lands and its refresh fails, memory holds the pre-save state while
disk holds the save. `save_codeagent` writes **complete layers from memory**, so
a second save would silently undo the first. A review simulation confirmed this:
pick=b/2 saved, refresh failed, then saving explore=c/3 restored pick=a/1. Assigning the unverified
written payload to memory would defeat all-or-nothing, so the family is
**latched** instead:

```python
class ConfigStaleError(ConfigReadError):
    """A write was refused: this family was saved but could not be re-read since."""

# ConfigManager.__init__
self._unrefreshed: set[str] = set()   # families saved but not re-read since

def refresh_after_write(self, family: str) -> None:
    """Re-read `family` after a save; on failure latch it and re-raise."""
    reload = {"codeagent": self.reload_codeagent, "board": self.reload_board,
              "project": self.reload_project_config}[family]
    try:
        reload()
    except ConfigReadError:
        self._unrefreshed.add(family)
        raise

def needs_reload(self, family: str) -> bool:
    return family in self._unrefreshed

def _require_refreshed(self, family: str, path) -> None:
    if family in self._unrefreshed:
        raise ConfigStaleError(path, "saved earlier but not re-read since; "
                               "reload (r) before saving again")
```

- **Cleared** only by a successful re-read of that family: `reload_codeagent`,
  `reload_board` or `reload_project_config` (`_unrefreshed.discard(family)`
  after assignment), or by `load_all` (`_unrefreshed.clear()` after
  assignment). A successful revert or `r` therefore releases it, and the memory
  it leaves then includes the earlier save.
- **Enforced in the writers** (backstop, so a future caller cannot skip it):
  `save_codeagent` and `save_codeagent_layer` → `_require_refreshed("codeagent",
  CODEAGENT_CONFIG)`; `save_board` → `"board"`; `save_project_settings` →
  `"project"`. Each check runs first, before anything touches disk.
- **Set only on a failed post-write refresh**, never on a plain write. The
  headless writer tests (`test_settings_commit_on_save.py`) call writers back to
  back without a reload and must keep working.
- **Rule: every re-read that follows a write that landed or may have landed goes
  through the latching path.** The audit of post-write re-reads found three
  shapes:
  1. The six save handlers (step 4) use `refresh_after_write(family)`.
  2. The superseded switch (`_switch_superseded`, ~2892). Its *pre*-write
     `reload_codeagent()` stays plain (nothing written yet; success clears the
     latch). Its *post*-write re-read becomes
     `self.config_mgr.refresh_after_write("codeagent")` when `status in
     ("switched", "write_failed")`; `write_failed` is included because
     `switch_codeagent_default` itself says the write may have landed. For
     `"changed"` (nothing written) it stays plain `reload_codeagent()`. The
     existing `except (OSError, ValueError)` branch and all three
     switch-specific notifications are unchanged (`ConfigReadError` is a
     `ValueError`). A probe confirmed the hole this closes: disk held the
     switched model, memory held the old one, no latch was set, and a later
     guarded save restored the old model.
  3. Import (`_handle_import`, both the success and the `ConfigImportPartialError`
     branches). It writes files, then calls `_reload_all_configs()`, which
     returns False on a malformed file and keeps the stale memory. The code's
     own comment warns that "a later save would write it back". Stricter
     validation makes this reachable for any imported shape error. Add
     `ConfigManager.refresh_all_after_write()`: it calls `load_all()`, and on
     **any** exception it latches every family and re-raises.
     `_reload_all_configs(*, after_write=False)` calls it when `after_write` is
     set, and both import branches pass `after_write=True`. The `r` action keeps
     `after_write=False`.
- `refresh_after_write` latches on any `Exception`, not just `ConfigReadError`:
  the write may have landed whatever the read failed with.
- **Families:** `codeagent`, `board`, `project` (`project_config.yaml`: Project
  and Tmux tabs), and `profiles`. Profiles join because `load_all` is their only
  bulk re-read. After a failed post-import reload, profile memory and the
  profile editor are stale, and `_save_profile` builds a whole file from them.
  Guards: the `save_profile` and `delete_profile` writers call
  `_require_refreshed("profiles", path)`, and the `_save_profile`,
  `_handle_new_profile` (after its cancel branch) and `_handle_delete_profile`
  handlers call `_may_save("profiles")` first. Only `load_all` success clears
  `profiles`, because there is no per-family profile reload. Shortcut saves
  (`lib/shortcut_persist.py`) read-modify-write the file fresh from disk, so
  they cannot write stale memory back and need no latch.

### 3. One reporting helper on `SettingsApp`

```python
def _refresh_after_save(self, family: str, done: str) -> bool:
    """Re-read `family` after a save already landed; report, never raise."""
    try:
        self.config_mgr.refresh_after_write(family)
    except ConfigReadError as exc:
        self.notify(f"{done}, but re-reading the config failed — {exc}. The "
                    "tab still shows the config last loaded, and further saves "
                    "here are refused until it is re-read: fix the file, then "
                    "press r to reload.", severity="error", timeout=10)
        return False
    return True

def _refresh_for_revert(self, reload) -> bool:
    try:
        reload()
    except ConfigReadError as exc:
        self.notify(f"Cannot revert — {exc}. Kept the config already loaded; "
                    "fix the file, then press r to reload.",
                    severity="error", timeout=10)
        return False
    return True

def _may_save(self, family: str) -> bool:
    """Refuse, before building any payload, a save on a latched family."""
    if not self.config_mgr.needs_reload(family):
        return True
    self.notify("Not saved — this config was saved earlier but could not be "
                "re-read since, so this edit would be built on stale data. Fix "
                "the file, then press r to reload.", severity="error", timeout=10)
    return False
```

Every save handler calls `_may_save(<family>)` first and returns when it is
False. The writers' `_require_refreshed` is the backstop behind it.

### 4. Audit and rewire every direct `load_all()` caller

Each handler re-reads **only the family it wrote or reverts** and populates only
its own tab, which is all it ever displayed. An unrelated bad file therefore no
longer blocks it at all, and a bad file in its own family is reported. The
startup call (614) and `_reload_all_configs` (4497, already handled) stay on
`load_all`.

| line | handler | guard + refresh | on success (unchanged) |
|---|---|---|---|
| 2959 | `_handle_agent_pick` (after `save_codeagent`) | `_may_save("codeagent")`; `_refresh_after_save("codeagent", …)` | `_populate_agent_tab` + "Saved {key} = {value} ({layer})" |
| 2990 | `_handle_launch_mode_pick` | same | same |
| 3004 | `_clear_user_override` | same (guard before the override lookup) | populate + "Cleared user override for {key}" |
| 3079 | `save_board_settings` (after `save_board`) | `_may_save("board")`; `_refresh_after_save("board", …)` | "Board settings saved" |
| 3084 | `_revert_board_settings` | `_refresh_for_revert(reload_board)` | populate + "Board settings reverted" |
| 3228 | `save_project_settings` | `_may_save("project")`; `_refresh_after_save("project", …)` | populate project tab + "Project config saved" |
| 3233 | `_revert_project_settings` | `_refresh_for_revert(reload_project_config)` | populate + "Project config reverted" |
| 3608 | `save_tmux_settings` | `_may_save("project")`; `_refresh_after_save("project", …)` | populate tmux tab + "Tmux settings saved" |
| 3613 | `_revert_tmux_settings` | `_refresh_for_revert(reload_project_config)` | populate + "Tmux settings reverted" |

Pattern: `if not self._may_save("board"): return` at the top, then after the
write `if self._refresh_after_save("board", "Board settings saved"):
self.notify("Board settings saved")`. When the refresh fails, the success
notification and the populate are both skipped, so the error is the only
message. The project and tmux tabs share the `"project"` family because they
write the same `project_config.yaml`.

**Detach the save payloads first (prerequisite for catch-and-continue).** The
staging code copies only the outer layer dict and then mutates the nested map
it shares with the loaded state:
- `_handle_agent_pick` and `_handle_launch_mode_pick` (both branches) and
  `_clear_user_override` do `dict(self.config_mgr.codeagent_local|_project)`
  followed by `…["defaults"][key] = value` / `del …["defaults"][key]`.
- `save_board_settings` does `merged = dict(self.config_mgr.board)` followed by
  `merged["settings"][…] = …`.

The loaded `codeagent_project`/`codeagent_local`/`board` are therefore changed in
place before the write. The merged `codeagent` is a deep copy and is not. So when
the refresh fails, the loaded representations disagree, even though the reload
methods assign nothing. A probe confirmed this: a cleared local override left
`codeagent_local == {"defaults": {}}` while `codeagent` still had `pick`, and a
second clear reported "no override". Fix: stage with `copy.deepcopy(...)`
instead of `dict(...)` at those four handlers (`copy` is already imported). On a
failed refresh, all loaded representations then stay exactly as they were before
the save. The project and tmux saves already copy the nested maps they mutate
(`dict(data.get("tmux") or {})`, `dict(existing_dp)`), so they are left as is.

Side effect: these handlers used to refresh every family in memory, and the
profiles too, while repopulating only their own tab. Now in-memory state for the
other families keeps matching what their tabs display, which is the more
consistent behaviour. `r` remains the full reload.

### 5. Entry point

The `__main__` block wraps `SettingsApp()` in `try/except ConfigReadError`,
prints `Cannot start Settings — {exc}` to stderr, and exits 1. This replaces a
traceback. A malformed file at boot (pre-existing for parse errors, and newly
reachable for the rare `columns: {}` case) then names the file cleanly.

### 6. Tests: `tests/test_settings_reload_all.py`

Extend the docstring's "What is pinned" list with the t1945 bullets.

`ReloadMalformedConfigTest` (App.run_test):
- `test_mistyped_defaults_keeps_loaded_state`: boot valid
  `{"defaults": {"pick": "a/1"}}`, snapshot `codeagent` and `codeagent_project`,
  write `{"defaults": null}`, press `r`. Then `assert_rejected(app,
  "codeagent_config.json")`, `'defaults'` and `null` appear in the error, and
  both snapshots are unchanged.
- `test_mistyped_local_defaults_is_named`: `codeagent_config.local.json` =
  `{"defaults": []}`. The error names the local file and not the project file.
- `test_mistyped_board_settings_keeps_running`: `board_config.json` =
  `{"settings": null}` names `board_config.json`, and `board` is unchanged.

New `SaveRevertRefreshTest(_Fixture)` (App.run_test; the reviewer's regression
and its siblings):
- `test_board_revert_ignores_unrelated_bad_config`: boot valid, write
  `codeagent_config.json` = `{"defaults": null}`, call `_revert_board_settings()`
  (the button handler's body). The app keeps running, there are no errors,
  "Board settings reverted" is notified, and `config_mgr.codeagent` is still the
  booted value (the bad file was never swapped in).
- `test_board_revert_reports_own_bad_config`: `board_config.json` =
  `{"columns": {}}`, then revert. One error names `board_config.json` and says
  "Cannot revert". "Board settings reverted" is not notified, the app is
  running, and `board` is unchanged.
- Failed-refresh-after-save tests. Each one monkeypatches the family's reload
  method (`reload_codeagent` / `reload_board` / `reload_project_config`, which
  is what `refresh_after_write` dispatches to, so the patch must be on the
  instance before the call) to raise `ConfigReadError(path, "x")`, snapshots the loaded state with
  `copy.deepcopy` before the save, and asserts three things **separately**:
  (a) **the write landed**: the file on disk carries the new value;
  (b) **the notification is accurate**: exactly one error, containing
  "\<done\>, but re-reading" and the file name, and the plain success message is
  absent;
  (c) **the loaded state is untouched**: every representation equals its
  snapshot.
  - `test_board_save_refresh_failure`: set the auto-refresh CycleField to a
    non-default value, then call `save_board_settings()`. For (c), `board`,
    `board_project` and `board_local` all equal their snapshots.
  - `test_clear_override_refresh_failure`: boot with project
    `{"defaults": {"pick": "p/1"}}` and local `{"defaults": {"pick": "a/1"}}`,
    then call `_clear_user_override("pick")`. For (a), the local file no longer
    holds `pick`. For (c), `codeagent`, `codeagent_project` and
    `codeagent_local` all equal their snapshots (local still has `pick: a/1`). A
    second `_clear_user_override("pick")` must be refused with "Not saved", must
    not report "No user override to clear", and must leave the file
    byte-identical. This is the reviewer's probe.
  - `test_agent_pick_refresh_failure_then_second_save` (the lost-write
    regression): `_editing_layer = "user"`, then
    `_handle_agent_pick({"key": "pick", "value": "b/2"})`. For (a), the local file
    has `b/2`. For (c), all three code-agent representations are unchanged.
    **Then** a second `_handle_agent_pick({"key": "explore", "value": "c/3"})`
    must be refused with a "Not saved" error: both layer files are
    byte-identical to after the first save, and the first save's `pick: b/2`
    survives on disk. **Then** un-patch the reload and press `r` (succeeds,
    releasing the latch). A third save of `explore=c/3` now lands, and disk holds
    both `pick: b/2` and `explore: c/3`. Repeat the first save for the `project`
    layer, which also mutates the local layer's `defaults` when it drops the
    override.
  - `test_project_save_refresh_failure_latches`: same shape for
    `save_project_settings()` then `save_tmux_settings()`, which share the
    `"project"` family. The second save is refused before `project_config.yaml`
    changes.
- `test_import_reload_failure_latches_all_families`: monkeypatch
  `settings_app.import_all_configs` to write `codeagent_config.json` =
  `{"defaults": null}` and return its path, then call
  `app._handle_import({"path": "x"})`. Assert: one "Cannot reload configs" error,
  the app is running, and `needs_reload` is True for all four families. A
  following `_handle_agent_pick`, `save_board_settings()` and
  `_save_profile(...)` (with a profile fixture) are each refused with "Not
  saved", and their files stay byte-identical. After the file is fixed, `r`
  releases every latch and a save lands. Repeat the first half with
  `import_all_configs` raising `ConfigImportPartialError` after writing.

In `tests/test_settings_superseded_models.py` (reusing its real switch fixture
and its `reload_codeagent` spy pattern at ~528):
- `test_switch_refresh_failure_latches_codeagent`: the spy lets the
  **pre**-write read succeed and makes the **post**-write read raise
  `ConfigReadError`. Run the actual switch action. Assert: the existing "Switched
  … but the tab could not refresh" notification is preserved; disk holds the new
  model and memory the old; `needs_reload("codeagent")` is True. An ordinary
  `_handle_agent_pick` on another op is then refused with "Not saved" and leaves
  both layer files byte-identical. After un-patching, `r` releases the latch and
  that save lands with the switched model still on disk. Also add a variant
  where `switch_codeagent_default` returns `"changed"` and the post-read fails:
  nothing is latched, because nothing was written.

- `test_writer_backstop_refuses_latched_family` (headless `ConfigManager`):
  make `reload_board` raise, so `refresh_after_write("board")` raises and
  latches. `save_board(...)` then raises `ConfigStaleError` and the file is
  untouched. After a successful `reload_board()`, `save_board` works again.
  `save_codeagent` is not affected by a `board` latch (the latch is per
  family).
- `test_project_revert_ignores_unrelated_bad_config`: a bad `board_config.json`
  leaves `_revert_project_settings()` completing cleanly. One test like this
  pins the project/tmux family, which shares `reload_project_config`.

`LoadAllLayersTest` (headless, table-driven with `subTest`):
- `test_mistyped_layer_rejected_and_state_kept`: rows of (file, payload,
  fragment): `codeagent_config.json {"defaults": null}`, `{"defaults": "x"}`,
  `codeagent_config.local.json {"defaults": [1]}`, `board_config.json
  {"columns": {}}`, `{"columns": ["now"]}` (fragment `'columns[0]'`),
  `board_config.local.json {"settings": []}`. For each row, `load_all()` raises
  `ConfigReadError` with `exc.path.name == file` and the fragment in `str(exc)`.
  The codeagent and board triples must equal the pre-call snapshot. The file is
  restored after each row.
- `test_family_reloads_validate_and_keep_state`: `reload_codeagent()` with
  `{"defaults": null}` and with a `[]` root, and `reload_board()` with
  `{"settings": null}`, each raise naming the file and leave their own state
  unchanged.
- `test_unvalidated_keys_still_load` (the over-strictness control):
  `board_config.json` = `{"column_order": "x", "columns": [{"id": "now"}]}` and
  `codeagent_config.json` = `{"defaults": {"pick": 5}}` still load.

**Red proof:** extract `git archive HEAD .aitask-scripts` into the scratchpad
and run a scratch copy of the test file with `REPO_ROOT` pointed there. The
App-level `r` tests and the headless tests must fail on pre-change code.
`test_board_revert_ignores_unrelated_bad_config` passes on pre-change code; that
is the reviewer's point, since today it is green only by accident. Its value is
that it would fail on "validation without step 4". Prove that with an in-scratch
mutant that keeps steps 1-2 and reverts the step-4 edit for
`_revert_board_settings` (no stash, no restore in the shared worktree). A
second in-scratch mutant puts the `dict(...)` staging back in
`_clear_user_override` and must make `test_clear_override_refresh_failure` fail
on (c).

## Verification

- `python3 tests/test_settings_reload_all.py`
- Every settings module individually: `test_settings_superseded_models.py` (the
  `reload_codeagent` consumer), `test_settings_commit_on_save.py` (the save
  handlers), `test_settings_project_config_value_types.py`,
  `test_settings_default_profiles_unknown_keys.py`, and the rest of
  `tests/test_settings*.py`
- `python3 tests/test_metadata_writer_inventory.py` (writer methods are unchanged
  and must stay inventoried)
- The red proof and mutant, as above.

## Step 9

Post-implementation: commit code and plan separately, then archive via the
standard Step 9 flow (current-branch mode, no merge).

## Risk

### Code-health risk: medium
- Nine handlers are rewired from the global `load_all` to per-family reloads.
  Each one stops refreshing other families' (undisplayed) in-memory state and
  the profiles. A reader that relied on that side refresh would see stale data.
  The audit found none: each handler populates only its own tab · severity:
  medium · → mitigation: inline post-phase handler_regression_sweep
- Validation is stricter at boot: an empty-iterable non-list `columns`
  (e.g. `{}`), which boots today only by accident, is now refused with a named
  error (step 5 makes that clean) · severity: low · → mitigation: inline
  post-phase over_strictness_control
- After any write whose re-read failed (save handlers, superseded switch,
  import), memory is behind disk. A further save in that family would build on
  the stale memory and undo the first write. This is
  prevented by the step-2b latch: the family refuses writes, at the handler and
  in the writer, until a successful re-read. The latch is the new state to get
  right: it must be cleared by every successful re-read path, and set only on a
  failed post-write refresh. Getting either wrong blocks saves forever or lets
  the lost write back in · severity: medium · → mitigation: inline post-phase
  latch_release_check
- `reload_codeagent` changes from `load_layered_config` to the per-layer reader,
  which changes its error type and message. Callers catch `ValueError`, and
  `ConfigReadError` is a `ValueError` · severity: low · → mitigation: none
  (covered by test_settings_superseded_models.py in Verification)

### Goal-achievement risk: low
None identified.

### Planned mitigations
- timing: post-phase | name: over_strictness_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: stricter boot validation | desc: negative-control test that unvalidated keys (column_order, non-string defaults values) still load
- timing: post-phase | name: latch_release_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: refresh latch set/clear correctness | desc: tests prove the latch releases via r (load_all), a revert, and the superseded switch's reload_codeagent, and that it is never set by a plain write (commit_on_save's back-to-back writes stay green)
- timing: post-phase | name: handler_regression_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: per-family reload rewiring | desc: run every tests/test_settings*.py module plus the writer inventory after the rewiring

### Post-phase (risk mitigations)
- **over_strictness_control**: `test_unvalidated_keys_still_load` (step 6) passes
  on the post-change code.
- **latch_release_check**: the third save in
  `test_agent_pick_refresh_failure_then_second_save` covers release via `r`. Add
  release via `_revert_board_settings()` to `test_writer_backstop…`'s app-level
  sibling, and assert `needs_reload("codeagent")` is False after a successful
  `reload_codeagent()`. `test_settings_commit_on_save.py` (back-to-back writes)
  must stay green, which proves a plain write never latches.
- **handler_regression_sweep**: run every `tests/test_settings*.py` module and
  `tests/test_metadata_writer_inventory.py` individually; all pass.

## Post-Review Changes

### Change Request 1 (2026-10-12 08:55)
- **Requested by user:** `_refresh_after_save`'s message claimed "The tab still shows the config last loaded", but editable controls keep their pending values (board auto-refresh showed 5 while memory stayed 0).
- **Changes made:** the sentence now reads "The loaded config could not be refreshed", keeping the saved-but-refresh-failed and further-save-refusal guidance.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`

## Final Implementation Notes
- **Actual work done:** All of steps 1-6, as approved. Shape validation lives in
  `_read_json_layer(path, shape)` through `_check_layer_shape`, with JSON-named
  types in the messages (`'defaults' must be a JSON object, got null`).
  Per-family readers `_read_codeagent_layers` / `_read_board_layers` /
  `_read_project_config` feed both `load_all` and the new
  `reload_codeagent` / `reload_board` / `reload_project_config`. The refresh
  latch (`_unrefreshed`, `refresh_after_write`, `refresh_all_after_write`,
  `needs_reload`, `_require_refreshed`, `ConfigStaleError`) has four families:
  codeagent, board, project and profiles. App helpers `_refresh_after_save` /
  `_refresh_for_revert` / `_may_save` are used by all nine former `load_all()`
  handlers, by the superseded switch's post-write re-read, and by both import
  branches (`_reload_all_configs(after_write=True)`). Save payloads are
  deep-copied. The `__main__` entry prints `Cannot start Settings — <file>: …`
  and exits 1 instead of a traceback.
- **Deviations from plan:** `save_codeagent_layer` is NOT latch-guarded. Its
  only caller, `switch_codeagent_default`, builds `data` from a fresh file read,
  so a guard could only refuse a safe write, and it would raise past that
  method's `except OSError`. The guards are on `save_codeagent`, `save_board`,
  `save_project_settings`, `save_profile` and `delete_profile`. The
  now-unused `load_layered_config` import was dropped from `settings_app.py`.
- **Issues encountered:** The plan went through four review rounds before
  approval: save/revert crash paths, shallow-copy staging, lost writes after a
  failed refresh, and the switch/import post-write re-reads. Each finding is
  pinned by a regression. Red proof: on `git archive HEAD`, every new test
  fails, and the mistyped-key tests fail with the original `AttributeError:
  'NoneType' object has no attribute 'keys'`/`'get'`. Two mutants (revert back
  on `load_all`; `dict(...)` staging in `_clear_user_override`) each fail their
  target test with the intended signal.
- **Key decisions:** The latch is set only by a failed re-read *after a write*,
  never by a plain write. That keeps the headless back-to-back writer tests
  valid; `test_plain_writes_never_latch` pins it. Only a successful re-read of
  the family (or `load_all`) releases it. `refresh_after_write` latches on any
  exception, because the write may have landed whatever the read failed with.
  `column_order` and the values inside `defaults` are deliberately not
  validated, since no Settings reader depends on them;
  `test_unvalidated_keys_still_load` pins that.
- **Upstream defects identified:** None

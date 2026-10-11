---
Task: t1938_fix_settings_reload_malformed_config_crash.md
Base branch: main
Output branch: main
---

# t1938 — Settings `r` (reload all) must survive a malformed config

## Context

Pressing `r` in `ait settings` runs `action_reload_configs` →
`_reload_all_configs` → `ConfigManager.load_all()`
(`.aitask-scripts/settings/settings_app.py:571`). `load_all` assigns
`self.codeagent` / `self.board` / … one at a time straight from
`load_layered_config` / `_load_json` / `load_yaml_config`, which raise
`JSONDecodeError` (malformed JSON), `OSError`, or `yaml.YAMLError` (malformed
`project_config.yaml`). Nothing catches, so the Settings app exits. Worse, a
failure half-way leaves the in-memory config partially replaced.

`ConfigManager.reload_codeagent()` (~662) already shows the all-or-nothing
pattern: read every layer into locals, then assign.

Because `r` could crash, t1921's refresh-failure message (~2843) says "fix the
file, then reopen Settings" and `tests/test_settings_superseded_models.py:576`
pins that "press r" is absent. Once `r` survives, that message can point at `r`.

## Implementation

### 1. `ConfigReadError` (settings_app.py, just above `class ConfigManager`)

```python
class ConfigReadError(ValueError):
    """A config file exists but could not be read or parsed.

    Carries the offending path so the caller can name it; subclasses
    ValueError so existing `(OSError, ValueError)` handlers still match.
    """

    def __init__(self, path, cause):
        self.path = Path(path)
        self.cause = cause
        super().__init__(f"{path}: {cause}")
```

### 2. `ConfigManager.load_all()` — all or nothing, naming the file

- Add a small static helper `_read(path, reader)` that calls `reader()` and
  re-raises `(OSError, ValueError, yaml.YAMLError)` as
  `ConfigReadError(path, exc) from exc`.
- Read every raising source into locals **before assigning anything**:
  `codeagent_project`, `codeagent_local` (each `_load_json`, wrapped with its
  own path), then the merged `codeagent` via `load_layered_config` (wrapped with
  the project path — it re-reads the same two files, so a failure there is a
  race), the same three for board, then `project_config` via `load_yaml_config`
  (wrapped with `PROJECT_CONFIG`).
- Models loop: unchanged (already swallows per-file and builds into a local —
  change it to build `models` locally and assign with the rest).
- Then assign all attributes, then `self.load_profiles()` (it never raises).
- Docstring: "Raises ConfigReadError naming the unreadable file and leaves the
  in-memory state untouched."

Startup (`ConfigManager.__init__` → `load_all`) keeps its current behaviour —
a malformed file at open still fails — only the exception type is now the
`ValueError` subclass with the path in its message. Out of scope here.

### 3. `SettingsApp._reload_all_configs()` returns bool

```python
def _reload_all_configs(self) -> bool:
    """Re-read every config from disk and repopulate the tabs.

    All or nothing: an unreadable file is reported and the current in-memory
    config and tabs are kept. Returns False in that case.
    """
    try:
        self.config_mgr.load_all()
    except ConfigReadError as exc:
        self.notify(f"Cannot reload configs — {exc}. Kept the config already "
                    "loaded; fix the file, then press r to reload.",
                    severity="error", timeout=10)
        return False
    ...populate calls unchanged...
    return True
```

`action_reload_configs`: notify "Configs reloaded from disk" only when it
returns True.

Import callers (`_handle_import`, ~4508/4515) keep calling it unchanged; they
now get an error notification instead of an exception. That also fixes the
partial-import path, where a raise inside the `except ConfigImportPartialError`
handler escaped the `try` (the sibling `except Exception` does not catch it)
and skipped `_commit_imported`.

### 4. t1921 message (~2843)

"…could read — fix the file, then reopen Settings." →
"…could read — fix the file, then press r to reload."
Flip `tests/test_settings_superseded_models.py:576` from
`assertNotIn("press r", …)` to `assertIn("press r", …)`.

### 5. Regression tests — `tests/test_settings_reload_all.py`

Fixture: extend `make_app`'s notify stub to also collect error-severity
messages in `self.errors`; update the module docstring's "What is pinned" list.

New class `ReloadMalformedConfigTest(_Fixture)`:
- `test_malformed_codeagent_keeps_running`: boot; overwrite
  `codeagent_config.json` with `{not json`; press `r` → `app.is_running`, one
  error naming `codeagent_config.json`, "Configs reloaded from disk" absent,
  tabs still populated.
- `test_failure_is_all_or_nothing`: boot; write a *valid* changed
  `codeagent_config.json` (`{"defaults": {"pick": "x/y"}}`) and a malformed
  `board_config.json` (read after codeagent); press `r` → in-memory
  `config_mgr.codeagent` / `codeagent_project` unchanged from before the
  press; error names `board_config.json`.
- `test_malformed_project_yaml`: `project_config.yaml` = `key: [unclosed` →
  no crash, error names `project_config.yaml` (YAMLError path).
- `test_reload_recovers_after_fix`: malformed → `r` (error) → restore a valid
  file with a new value → `r` → "Configs reloaded from disk" and the new value
  is in `config_mgr.codeagent`.

## Verification

```bash
python3 tests/test_settings_reload_all.py
python3 tests/test_settings_superseded_models.py
python3 tests/test_settings_commit_on_save.py
bash tests/run_all_python_tests.sh --test-dir <dir with settings tests>   # or full suite
```
Red proof: with the step-2/3 changes reverted locally (scratch copy, not
`git stash`), the new malformed tests fail (app not running).

## Step 9

Post-implementation: commit code + tests (`bug: … (t1938)`), archive per
task-workflow Step 9.

## Risk

### Code-health risk: low
- None identified. The change is confined to `ConfigManager.load_all`,
  `_reload_all_configs` and `action_reload_configs`; the only other callers
  (import paths) move from an uncaught exception to an error notification, and
  existing reload/commit tests cover the success path.

### Goal-achievement risk: low
- None identified. The defect is reproduced directly by the new `App.run_test`
  regressions (JSON and YAML cases plus the all-or-nothing invariant).

## Final Implementation Notes

- **Actual work done:** Steps 1–5 as planned. `ConfigReadError(ValueError)` plus a
  module-level `_read_config(path, reader)` helper (rather than a static method)
  sit above `ConfigManager`; `load_all()` reads every raising source into locals,
  assigns only after all succeed, then calls `load_profiles()`.
  `_reload_all_configs()` returns bool and notifies a single error naming the
  file; `action_reload_configs` reports success only on True. t1921's
  refresh-failure message now says "fix the file, then press r to reload" and
  `test_settings_superseded_models.py:576` asserts "press r" is present.
- **Deviations from plan:** the models accumulator is named `all_models` — the
  existing loop already binds `models` to each file's list, and reusing the name
  clobbered the dict (caught by the first test run).
- **Issues encountered:** none beyond the name clash above.
- **Key decisions:** the catch lives in `_reload_all_configs`, not only in the
  action, so both import paths also survive an unreadable file (the partial
  import path previously let the exception escape its `except` handler and skip
  `_commit_imported`). Startup with a malformed file still fails at open —
  unchanged, out of scope.
- **Upstream defects identified:**
  - `.aitask-scripts/settings/settings_app.py:2428 — a well-formed layer with a wrong-typed value (e.g. codeagent_config.json {"defaults": null}) passes ConfigManager.load_all, replaces the loaded state, and then crashes _populate_agent_tab with AttributeError ('NoneType' object has no attribute 'keys') outside the reload's error handling; pre-existing (the pre-t1938 load_all accepted it too). Validate the defaults mapping per layer before assignment, name the offending file, and add a regression that keeps the loaded state`
- **Verification:** `tests/test_settings_reload_all.py` 7/7 OK; red proof — the
  4 new tests fail against HEAD's `settings_app.py` (loaded from a scratch copy)
  with `JSONDecodeError` / YAML `ParserError` and `app.is_running` False. All
  `tests/test_settings_*.py` modules and the other modules importing
  `settings_app` pass.

## Post-Review Changes

### Change Request 1 (2026-10-11)
- **Requested by user:** `load_all` read each project/local layer and then
  re-read both through `load_layered_config` under a wrapper labelled with the
  project path, so a local layer that went bad between the two reads was
  reported as the project file (codeagent and board pairs). Merge the
  already-read layers with `deep_merge`, keeping defaults and override
  precedence, and cover local-file attribution.
- **Changes made:** `_read_json_layer(path)` reads each JSON layer once under
  its own path and rejects a non-object layer (`[]` would otherwise crash the
  merge with an uncaught `AttributeError`). `_merge_layers(defaults, project,
  local)` reproduces `load_layered_config`'s merge (deepcopy defaults, then
  `deep_merge` project, then local, each only when non-empty) on the
  already-read dicts; `load_all` no longer calls `load_layered_config`. New
  tests: broken `codeagent_config.local.json` / `board_config.local.json` are
  named (and the project file is not), a `[]` layer is rejected, each of the
  four JSON layers is read exactly once (counting both `settings_app` and
  `config_utils` `_load_json` bindings — red against the double-read version),
  and the merged result equals `load_layered_config`'s for both configs with
  local-over-project precedence.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`,
  `tests/test_settings_reload_all.py`

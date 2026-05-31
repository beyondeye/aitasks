---
Task: t863_fix_keybinding_registry_yaml_guard.md
Base branch: main
plan_verified: []
---

# Plan: Guard `load_user_overrides()` against malformed userconfig.yaml (t863)

## Context

`keybinding_registry.load_user_overrides()` calls `yaml.safe_load(f)` with no
exception handling (`.aitask-scripts/lib/keybinding_registry.py:51-52`). A
malformed (gitignored) `aitasks/metadata/userconfig.yaml` therefore raises a
`yaml.YAMLError` that propagates up through every TUI's module-level
`register_app_bindings(...)` call chain (`tui_switcher.py` →
`register_app_bindings` → `load_user_overrides`), crashing every board/TUI at
**import time**. This actually happened during t832_8 import-smoke-testing (a
dangling `- agentcrew` block item after `last_used_labels: [codexcli]`).

The function already guards the **missing-file** case (`if not path.is_file():
return {}`) but not the **malformed-content** case. A per-user override file
that fails to parse should degrade to "no overrides" — not bring down the TUI.

## Fix

**File: `.aitask-scripts/lib/keybinding_registry.py`**

1. Add `import sys` to the top-level stdlib imports (module currently imports
   only `dataclasses`, `pathlib.Path`, `typing.Any`).

2. Wrap the `yaml.safe_load(f)` read in `load_user_overrides()` in a
   `try/except yaml.YAMLError`, mirroring the existing missing-file fallback:
   on parse failure, write a one-line warning to stderr, cache `{}`, and
   return it.

   ```python
       import yaml  # local import: tests may run before yaml is on sys.path

       try:
           with open(path, "r", encoding="utf-8") as f:
               data = yaml.safe_load(f) or {}
       except yaml.YAMLError as exc:
           # A malformed (gitignored) userconfig.yaml must not crash every
           # board/TUI at import time; degrade to "no overrides" like the
           # missing-file case above.
           sys.stderr.write(
               f"keybinding_registry: ignoring malformed {path}: {exc}\n"
           )
           _OVERRIDES_CACHE = {}
           return _OVERRIDES_CACHE
       shortcuts = data.get("shortcuts") or {}
   ```

   Caching `{}` matches the missing-file path and avoids re-parsing /
   re-warning on every subsequent call.

## Test

**File: `tests/test_keybinding_registry.sh`** — add a Case 7 following the
existing `run_py` / `write_userconfig` pattern:

- `write_userconfig "case7"` with a malformed body (dangling block-sequence
  item after a mapping key, mirroring the real corruption):
  ```
  last_used_labels: [codexcli]
  - agentcrew
  ```
- Python: capture stderr via `contextlib.redirect_stderr`, call
  `load_user_overrides()`, assert it returns `{}` (no exception raised) and
  that the captured stderr contains `malformed`. Print `OK`.

This proves the regression is fixed: parse failure no longer raises, falls
back to `{}`, and emits the warning.

## Verification

```bash
bash tests/test_keybinding_registry.sh        # all 7 cases PASS
```

Additionally, an import smoke-test mirroring the original crash:
```bash
# with a deliberately malformed aitasks/metadata/userconfig.yaml present,
# importing the registry no longer raises
PYTHONPATH=.aitask-scripts/lib python -c "import keybinding_registry as k; print(k.load_user_overrides())"
```

No skill `.md.j2` / closure edits, so no goldens to regenerate. `keybinding_registry.py`
is a Python module (not in `./ait`'s source chain), so the test-scaffold lib
list is unaffected.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. (1) Added `import sys`
  to `keybinding_registry.py` top-level imports. (2) Wrapped the
  `yaml.safe_load(f)` read in `load_user_overrides()` in
  `try/except yaml.YAMLError`; on parse failure it writes a one-line warning
  (`keybinding_registry: ignoring malformed <path>: <exc>`) to stderr, caches
  `_OVERRIDES_CACHE = {}`, and returns it — mirroring the existing missing-file
  fallback. (3) Added Case 7 to `tests/test_keybinding_registry.sh`: a
  malformed userconfig (dangling block-sequence item after a mapping key) is
  loaded with stderr captured via `contextlib.redirect_stderr`; asserts the
  result is `{}` and the warning contains `malformed`.
- **Deviations from plan:** None.
- **Issues encountered:** None. All verification passed first time:
  `test_keybinding_registry.sh` 7/7, `test_shortcut_editor_modal.py` 14/14,
  `test_shortcuts_registry_coverage.sh` PASS, and an isolated import
  smoke-test with a deliberately malformed userconfig confirmed the warning
  fires and `{}` is returned instead of a crash.
- **Key decisions:** Cached `{}` on parse failure (not just returned it) so a
  corrupt file does not re-parse / re-warn on every subsequent call, matching
  the missing-file path. Left `config_utils.load_yaml_config` untouched — it
  deliberately raises on invalid YAML because project-scoped config corruption
  should be a hard error; only the gitignored per-user override file degrades
  gracefully.
- **Upstream defects identified:** None.

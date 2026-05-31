---
Task: t865_fix_shortcut_persist_yaml_guard.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan: Guard userconfig.yaml `_load_full()` against malformed YAML (t865)

## Context

t863 fixed an unguarded `yaml.safe_load` in `keybinding_registry.load_user_overrides()`
that crashed every TUI at import time. The Step 8b sanity-check flagged the sibling
helper `shortcut_persist._load_full()` as having the same defect class. **Since then,
the t864 refactor moved `_load_full()` / `_atomic_dump()` into a single shared module
`userconfig_persist.py`** — the canonical persistence layer for `userconfig.yaml`. So
the actual unguarded `yaml.safe_load` now lives at **`userconfig_persist.py:69`**, not
in `shortcut_persist.py` (the task text predates the refactor).

A malformed (gitignored) `userconfig.yaml` therefore raises `yaml.YAMLError` out of
`_load_full()`, crashing every caller. `_load_full()` is now shared by **both**:
- **Write paths** (round-trip the whole file via `_atomic_dump`): `shortcut_persist.save_override` / `clear_override` / `reset_scope`, and `userconfig_persist.set_last_used_labels`.
- **Read path**: `userconfig_persist.get_last_used_labels`.

This sharpens the task's stated nuance: a naive `{}` fallback (the t863 read-side fix)
is **wrong here** — a write path would then round-trip `{}` back to disk via
`_atomic_dump`, **erasing the user's `email`, `shortcuts`, and `last_used_labels`**.

**Decision (per the task's "decide accordingly"):** `_load_full()` raises a *typed*
exception on malformed content (distinct from the legitimate missing-file → `{}` case).
**Write paths fail loud** (abort, surface a clear message, write nothing). The single
**read path degrades gracefully** to its default (mirroring t863). The data-loss path
is closed because `_load_full()` raises *before* any `_atomic_dump` runs.

## Changes

### 1. `.aitask-scripts/lib/userconfig_persist.py` — the fix

- **Add a typed exception** (module level, after imports):
  ```python
  class MalformedUserConfigError(Exception):
      """Raised when userconfig.yaml exists but is not parseable YAML.

      Distinct from the missing-file case (which legitimately yields {}). Write
      paths must surface this rather than round-trip an empty dict, which would
      erase the user's other top-level keys (email, last_used_labels, shortcuts).
      """
  ```
- **Guard `_load_full()` (lines 64-70):** wrap only the `yaml.safe_load` call; keep the
  missing-file early return (`{}`) and the non-dict normalisation unchanged:
  ```python
  with open(path, "r", encoding="utf-8") as f:
      try:
          data = yaml.safe_load(f) or {}
      except yaml.YAMLError as exc:
          raise MalformedUserConfigError(
              f"{path} is not valid YAML: {exc}"
          ) from exc
  ```
- **Read-side degrade in `get_last_used_labels()` (lines 105-115):** wrap the
  `_load_full()` call in `try/except MalformedUserConfigError`, write a one-line
  warning to `sys.stderr` (mirrors t863 wording), and `return []`.
- **CLI fail-loud in `_main()` (lines 129-143):** wrap the command dispatch in
  `try/except MalformedUserConfigError`, print `userconfig_persist: <msg>` to stderr,
  and `return 1`. This keeps the `set-labels` subcommand from dumping a raw traceback;
  `set_last_used_labels()` itself stays unguarded so it propagates (fail-loud). (`sys`
  is already imported.)

### 2. `.aitask-scripts/lib/shortcut_persist.py` — no logic change

The three write functions already call `_load_full()` first, so they now propagate
`MalformedUserConfigError` *before* `_atomic_dump` — exactly the desired fail-loud.
No edit needed to the function bodies. The interactive caller imports the exception
directly from `userconfig_persist` (see #3), so no re-export is required here.

### 3. `.aitask-scripts/lib/shortcut_editor_modal.py` — interactive fail-loud (lines 246-270)

`action_save()` loops over pending edits calling `clear_override` / `save_override`.
Wrap the persistence loop in `try/except MalformedUserConfigError`: on error, call
`self.app.notify(<clear message>, severity="error", timeout=...)` and `return`
*without* dismissing the modal (so pending edits survive and the user can cancel/fix).
Skip the success path (registry refresh, `refresh_bindings`, success notify, dismiss).
The first `_load_full()` raises before any write, so nothing is partially persisted.
Add `from userconfig_persist import MalformedUserConfigError` to the imports.

### Bash wrappers — no change needed
`task_utils.sh::get_last_used_labels` already swallows a non-zero Python exit and falls
back to a read-only grep; `set_last_used_labels` falls back to the **block-safe**
`_set_last_used_labels_fallback` (a targeted line-edit that never round-trips the whole
file), so the data-loss path does not exist through bash. Left as-is.

## Tests

- **`tests/test_keybinding_registry.sh`** — add **Case 8** (write-path fail-loud):
  reuse Case 7's malformed fixture (`last_used_labels: [codexcli]\n- agentcrew`); assert
  `shortcut_persist.save_override(...)` raises `MalformedUserConfigError` and the file is
  **byte-for-byte unchanged** (not overwritten to `{}`). Add **Case 9** (userconfig_persist
  directly): `set_last_used_labels(...)` raises `MalformedUserConfigError` (write fail-loud,
  file unchanged); `get_last_used_labels()` returns `[]` with a stderr warning (read degrade).
  Extend the file header comment to mention `userconfig_persist`.
- **`tests/test_last_used_labels.sh`** — add a case: malformed `userconfig.yaml` →
  `get_last_used_labels` (bash wrapper) returns empty without crashing (read degrade end-to-end).
- **`tests/test_shortcut_editor_modal.py`** — add a `ModalLogicTests` test: with a malformed
  `userconfig.yaml`, `action_save()` calls `app.notify` with `severity="error"`, does **not**
  call `dismiss`, and leaves the file unchanged.

No golden files change (rendering output is untouched). No new system lib is added to
`./ait`'s source chain, so `tests/lib/test_scaffold.sh` needs no update.

## Verification

```bash
# Targeted unit tests
bash tests/test_keybinding_registry.sh
bash tests/test_last_used_labels.sh
bash tests/test_userconfig_writer_collision.sh
PYTHONPATH=.aitask-scripts/lib python3 -m pytest tests/test_shortcut_editor_modal.py  # or run directly

# Lint
shellcheck tests/test_keybinding_registry.sh tests/test_last_used_labels.sh

# Manual smoke (data-loss regression): malformed file + a write must NOT erase it
cd "$(mktemp -d)" && mkdir -p aitasks/metadata
printf 'email: me@x.test\nlast_used_labels: [a]\n- orphan\n' > aitasks/metadata/userconfig.yaml
PYTHONPATH=<repo>/.aitask-scripts/lib python3 -c \
  "import shortcut_persist as sp; sp.save_override('board','pick','o')"   # expect MalformedUserConfigError, file intact
cat aitasks/metadata/userconfig.yaml   # email + last_used_labels still present
```

Then Step 9 (Post-Implementation): commit, archive, merge per task-workflow.

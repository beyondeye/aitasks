---
Task: t864_fix_userconfig_yaml_writer_style_collision.md
Base branch: main
plan_verified: []
---

# Plan: Fix userconfig.yaml writer style collision (t864)

## Context

`aitasks/metadata/userconfig.yaml` (per-user, gitignored) has **two writers
with incompatible YAML styles**, and their interaction silently corrupts the
file — which crashes **every** TUI at import time (`tui_switcher` →
`keybinding_registry.load_user_overrides()` reads the file at module import).

1. **bash** `set_last_used_labels()` (`.aitask-scripts/lib/task_utils.sh:384-411`)
   writes **flow** style (`last_used_labels: [a, b]`) and, when the field
   already exists, `sed`-replaces only the single `last_used_labels:` header
   line.
2. **Python** `shortcut_persist._atomic_dump()`
   (`.aitask-scripts/lib/shortcut_persist.py:39-63`, the t848 shortcut editor)
   round-trips the **whole file** with `yaml.safe_dump(default_flow_style=False)`,
   rewriting `last_used_labels: [codexcli]` as a multi-line **block** list.

When the Python writer runs first (file becomes block style) and a later bash
`set_last_used_labels` runs, its `sed` rewrites only the header line and
**orphans the `- item` continuation lines** → invalid YAML.

**Reproduced against current code** (confirmed during planning): a block-style
`last_used_labels` followed by a `shortcuts:` block, after one bash
`set_last_used_labels "codexcli"`, becomes:

```yaml
last_used_labels: [codexcli]
- agentcrew          # orphaned → ParserError at this line
shortcuts:
  board:
    pick: p
```

**Goal:** make both writers agree on a single safe representation and stop
line-based editing of a multi-line YAML value, so this class of corruption is
impossible. (t863 separately hardens the *reader* with try/except — out of
scope here, do not fold.)

## Approach (the task's "Preferred" option: one Python persistence module)

Route `last_used_labels` read/write through the **same yaml-aware
whole-file round-trip** that `shortcut_persist` already uses, consolidating both
writers onto one persistence module. The on-disk format for `last_used_labels`
stays **flow** (`[a, b]`) — preserving the existing format and the existing
`test_last_used_labels.sh` assertions — while `shortcuts:` stays block. Because
every write goes through one `yaml.safe_dump`, no path ever line-edits YAML, so
the orphaned-continuation bug cannot recur.

### 1. New `.aitask-scripts/lib/userconfig_persist.py` — single persistence layer

Owns the generic `userconfig.yaml` plumbing (moved out of `shortcut_persist.py`)
plus `last_used_labels` accessors and a small CLI for bash:

- `_USERCONFIG_HEADER` (moved here).
- `_userconfig_path()` — honors `TASK_DIR` env (default `aitasks`) so bash and
  the tests can target an isolated dir:
  `Path(os.environ.get("TASK_DIR", "aitasks")) / "metadata" / "userconfig.yaml"`.
  (Unset `TASK_DIR` → `aitasks`, identical to today's hardcoded path, so the
  TUI/`test_shortcut_editor_modal.py` chdir-based usage is unaffected.)
- `_load_full()` — as today (`yaml.safe_load`, returns `{}` on missing/non-dict).
- `_atomic_dump(data)` — as today (temp file + `os.replace`, header only for new
  files), **plus a flow-style policy**: any `last_used_labels` list is emitted in
  flow style via a `_FlowList(list)` subclass + a `SafeDumper` representer
  (`represent_sequence(..., flow_style=True)`). `_atomic_dump` normalizes
  `data["last_used_labels"]` to `_FlowList` before dumping (non-mutating copy), so
  **both** the shortcut writer and the label writer emit identical
  `last_used_labels: [a, b]` while `shortcuts:` stays block.
- `get_last_used_labels() -> list[str]` and `set_last_used_labels(labels) -> None`.
- `__main__` CLI: `get-labels` (prints comma-joined CSV) and
  `set-labels <csv>` (empty arg → `[]`). Imports only `yaml` + stdlib (no
  `keybinding_registry`), so the bash CLI call is lightweight.

### 2. Refactor `.aitask-scripts/lib/shortcut_persist.py` to share the module

Replace its local `_userconfig_path`/`_load_full`/`_atomic_dump`/`_USERCONFIG_HEADER`
with `from userconfig_persist import (...)`. Keep the public API unchanged
(`save_override`, `clear_override`, `reset_scope` + `keybinding_registry.refresh`).
Callers only use the public API (verified: `shortcut_editor_modal.py`,
`brainstorm_app.py`'s `_load_full` is its own unrelated method). This guarantees
the two writers produce **byte-identical** formatting for shared keys.

### 3. Rewrite the bash helpers in `task_utils.sh` to delegate to Python

- Source `lib/python_resolve.sh` (guarded) in the `task_utils.sh` source block
  to get `resolve_python` (already in the lib dir; `SCRIPT_DIR` is `.aitask-scripts`).
- `get_last_used_labels()`: call
  `TASK_DIR=... "$py" "$SCRIPT_DIR/lib/userconfig_persist.py" get-labels`
  when Python resolves; on no-Python/failure fall back to the current
  grep+sed **flow-only read** (harmless, read-only).
- `set_last_used_labels()`: call `... set-labels "$csv"` when Python resolves;
  on no-Python/failure fall back to a **block-safe** bash writer — same flow
  output as today **plus** an `awk` pass that drops orphaned `^- item`
  continuation lines after the header (stops at the first non-list line, so a
  following `shortcuts:` block is never touched). The old single-line `sed`
  (the corruption source) is removed entirely.

This keeps `ait create` working with or without the venv Python and makes
corruption impossible on every path.

### 4. New regression test `tests/test_userconfig_writer_collision.sh`

Self-contained bash test (`assert_eq`/`assert_contains`, PASS/FAIL summary),
sources `tests/lib/venv_python.sh` for `$AITASK_PYTHON` and
`task_utils.sh` against an isolated `TASK_DIR`:

- **Block-then-bash:** write a block-style `last_used_labels` (+ a `shortcuts:`
  block), run `set_last_used_labels "codexcli"`, assert the file still parses
  (`$AITASK_PYTHON -c "import yaml; yaml.safe_load(...)"`), labels round-trip via
  `get_last_used_labels`, and `shortcuts:` survived.
- **Python-then-bash end-to-end:** drive the Python writer
  (`userconfig_persist.set_last_used_labels` + a `shortcuts` entry via
  `_atomic_dump`, the realistic shortcut-save on-disk shape) then run bash
  `set_last_used_labels`, assert the file remains valid YAML.
- **get reads both styles:** assert `get_last_used_labels` returns the right CSV
  for a flow file and for a block file.
- Confirm the suite **fails against current code** (the block-then-bash case
  already corrupts, as reproduced) and **passes after the fix**.

## Files

| File | Change |
|------|--------|
| `.aitask-scripts/lib/userconfig_persist.py` | **new** — shared persistence + `last_used_labels` accessors + CLI |
| `.aitask-scripts/lib/shortcut_persist.py` | import shared internals from `userconfig_persist`; drop local copies |
| `.aitask-scripts/lib/task_utils.sh` | source `python_resolve.sh`; rewrite `get/set_last_used_labels` to delegate to Python with safe fallbacks |
| `tests/test_userconfig_writer_collision.sh` | **new** regression test (required) |

Not touched: `keybinding_registry.py` (reader hardening = t863).
No change to `ait`'s source-on-startup chain or `tests/lib/test_scaffold.sh`
(the new lib is invoked on demand, not sourced by `ait`).

## Verification

```bash
bash tests/test_userconfig_writer_collision.sh   # new — must pass
bash tests/test_last_used_labels.sh              # existing flow-style contract — still passes
python3 -m unittest tests.test_shortcut_editor_modal  # shortcut persistence unaffected
shellcheck .aitask-scripts/lib/task_utils.sh
```
Plus the end-to-end manual repro (Python shortcut-save → `ait create`) leaves a
valid, parseable `userconfig.yaml`.

## Notes / decision

- This follows the task's **Preferred** option (one Python persistence module),
  not the Minimal bash-only one, because it removes YAML line-editing entirely —
  the root cause — and consolidates both writers. The flow-style policy keeps the
  on-disk format and all existing tests intact.
- The bash safe-fallbacks mean label memory keeps working even without the venv
  Python (graceful degradation, never corrupting).
- Comment-preservation: like `shortcut_persist` today, a yaml round-trip of an
  existing file drops inline comments (header re-added only for new files). This
  matches established shortcut-editor behavior.
- Commit type: `bug: ... (t864)`.

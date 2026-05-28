---
Task: t848_1_shortcut_registry_and_overrides.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_2_*.md, aitasks/t848/t848_3_*.md, aitasks/t848/t848_4_*.md, aitasks/t848/t848_5_*.md, aitasks/t848/t848_6_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
---

# p848_1 — Shortcut registry + user-overrides layer

## Goal

Library-only foundation: a registry that records every TUI's bindings
and a persistence layer that reads/writes per-user overrides in
`aitasks/metadata/userconfig.yaml`. No TUI is touched in this task.

## Files

**New:**

- `.aitask-scripts/lib/keybinding_registry.py`
- `.aitask-scripts/lib/shortcut_persist.py`
- `tests/test_keybinding_registry.sh`

**Modified:** none.

## Step-by-step

### 1. `keybinding_registry.py`

Module state:

```python
_DEFAULTS: dict[tuple[str, str], tuple[str, str]] = {}  # (scope, action_id) -> (default_key, label)
_OVERRIDES_CACHE: dict[str, dict[str, str]] | None = None  # scope -> {action_id: key}
```

API:

```python
def register_app_bindings(scope: str, bindings: list[Binding]) -> list[Binding]:
    """Record defaults from bindings; return a new list with user overrides applied."""

def load_user_overrides() -> dict[str, dict[str, str]]:
    """Read userconfig.yaml `shortcuts:` key. Cached. Returns {} if absent."""

def resolve_key(scope: str, action_id: str, default_key: str | None = None) -> str | None:
    """Look up the effective key. Returns override, else recorded default, else default_key arg, else None."""

def coherence_lint(scopes_to_check: list[str] | None = None) -> list[str]:
    """For each SHARED_ACTION_IDS entry, group scopes by effective key; emit warning if >1 group."""

def refresh(scope: str | None = None) -> None:
    """Invalidate the override cache; next call to load_user_overrides re-reads disk."""

SHARED_ACTION_IDS = frozenset({"quit", "tui_switcher", "refresh", "shortcuts_editor"})
```

Binding mutation: Textual's `Binding` is a frozen dataclass; use
`dataclasses.replace(b, key=new_key)`. (Confirmed via Textual source.)

### 2. `shortcut_persist.py`

```python
def save_override(scope: str, action_id: str, key: str) -> None: ...
def clear_override(scope: str, action_id: str) -> None: ...
def reset_scope(scope: str) -> None: ...
```

Implementation:

- Read existing `userconfig.yaml` via `yaml.safe_load` (or fall back
  to `{}` if file missing — but the file should already exist since
  it has `email:` / `last_used_labels:` from picker workflow).
- Deep-merge the shortcut change into `data.setdefault("shortcuts", {})[scope]`.
- Atomic write: `yaml.safe_dump` into a tempfile in the same dir, then
  `os.replace(tmp, path)`.
- After write, call `keybinding_registry.refresh(scope)`.

### 3. `tests/test_keybinding_registry.sh`

Use `tests/lib/test_scaffold.sh` + small Python `-c` invocations. One
temp `userconfig.yaml` per case. Assertions cover the six cases listed
in the task description.

Confirm whether `./ait` sources `lib/keybinding_registry.py` at startup
(it should not — only TUIs need it). If it does **not**, no
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` update is
needed. If it does, add `keybinding_registry.py` to the scaffolded
`.aitask-scripts/lib/` (per CLAUDE.md baseline rule).

## Verification

```bash
bash tests/test_keybinding_registry.sh    # all PASS
shellcheck tests/test_keybinding_registry.sh
```

## Verification (for the t848_7 manual-verification sibling)

- None — pure library task; covered by unit tests.

## Step 9 — Post-implementation

Standard archival. Plan + code commit separated per CLAUDE.md.

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/lib/keybinding_registry.py`
  (registry + override resolver + `coherence_lint` + `SHARED_ACTION_IDS` +
  `refresh`/`refresh_all` + `_reset_for_tests`),
  `.aitask-scripts/lib/shortcut_persist.py` (`save_override`,
  `clear_override`, `reset_scope` with atomic `os.replace` write +
  preservation of sibling top-level keys), and
  `tests/test_keybinding_registry.sh` (6 cases, all passing).
- **Deviations from plan:** Two minor adjustments.
  1. `shortcut_persist.py` imports `keybinding_registry` as a top-level
     module (`import keybinding_registry`), not via package-relative
     `from . import keybinding_registry`. Reason below in "Key decisions".
  2. Added a small `_reset_for_tests()` helper to `keybinding_registry`
     so each test case starts from a clean `_DEFAULTS` map and a cold
     override cache. Not in the plan but trivial and test-only.
- **Issues encountered:** None significant. Initial shellcheck run flagged
  SC1091 (info) on the `source "$SCRIPT_DIR/lib/venv_python.sh"` line; this
  matches the existing convention (`tests/test_agentcrew_terminal_push.sh`
  and others have the identical info-level message). Treated as accepted
  baseline noise rather than a real warning.
- **Key decisions:**
  - **Module-not-package imports.** `.aitask-scripts/lib/` is added to
    `sys.path` (see `.aitask-scripts/board/aitask_board.py:13`); modules
    in it are imported as top-level names, not as members of a `lib`
    package. So `shortcut_persist` uses `import keybinding_registry`.
    **Sibling tasks consuming these modules must do the same.**
  - **PyYAML, not ruamel.** `ruamel.yaml` is not vendored anywhere in
    `.aitask-scripts/`; `config_utils.py` uses PyYAML `safe_load`/`safe_dump`.
    No comments are preserved on round-trip — accepted, matches existing
    config helpers.
  - **Atomic write done in-module.** `config_utils.save_yaml_config` writes
    directly (not atomic), so `shortcut_persist._atomic_dump` rolls its
    own `tempfile.mkstemp` + `os.replace` rather than reusing the helper.
    Userconfig header (`# Local user configuration (gitignored, not shared)`)
    is emitted only when the file is being created fresh.
  - **`Binding` mutation API.** Confirmed at runtime that
    `textual.binding.Binding` is a `@dataclass(frozen=True)`; mutation goes
    through `dataclasses.replace(b, key=new_key)`. **t848_2's
    `ShortcutsMixin` should rely on this — do not try to assign
    `b.key = …` directly.**
  - **`coherence_lint` semantics.** The current implementation iterates
    `SHARED_ACTION_IDS`, gathers the effective key per scope where that
    action is registered, and emits a warning only when more than one
    distinct key is in use. Scopes that never registered the action are
    skipped. The warning format is one line like
    ``"`quit` is bound to `q` in scopeA, `x` in scopeB"``.
- **Test scaffolding.** Each Python sub-case runs in its own
  `mktemp -d`/subdir CWD with a freshly-written `aitasks/metadata/userconfig.yaml`
  and `PYTHONPATH=.aitask-scripts/lib`. Pattern lifted from
  `tests/test_aitask_projects_doctor.sh`. No use of
  `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` was needed —
  these tests don't drive `./ait`, only call the new modules directly.
- **Scaffold update NOT required.** Confirmed via `grep -n "lib/" ait`
  that `./ait`'s source-on-startup chain is only
  `aitask_path.sh`/`terminal_compat.sh`/`python_resolve.sh` (plus
  `yaml_utils.sh` per the scaffold), with `task_utils.sh` sourced on the
  `git`/`git-health` subcommand paths. Neither `keybinding_registry.py`
  nor `shortcut_persist.py` is touched by `./ait`, so
  `setup_fake_aitask_repo()` does not need an update for this task.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t848_2 (ShortcutsMixin / board pilot):**
    - Call `register_app_bindings("board", BINDINGS)` and assign the
      result to the App's `BINDINGS` class attribute (or use the returned
      list when constructing it dynamically). The function records the
      defaults *and* returns the overrides-applied list — both effects in
      one call.
    - For label rendering outside of a `Binding` (e.g. status-bar text),
      use `keybinding_registry.resolve_key("board", "<action_id>",
      default_key="<fallback>")`. Falls back gracefully when nothing is
      registered.
    - After persisting an override via `shortcut_persist.save_override`,
      the registry cache is invalidated automatically (`refresh(scope)`
      is called at the end of `save_override`/`clear_override`/`reset_scope`).
      Re-construct the App's `BINDINGS` to pick up the new mapping.
    - `Binding` is frozen → use `dataclasses.replace(b, key=new_key)` for
      any further mutation. Don't try direct attribute assignment.
  - **t848_3 (TUI sweep):** Same `register_app_bindings` call per App.
    Choose a consistent `scope` string per TUI (suggested:
    `board`, `monitor`, `minimonitor`, `codebrowser`, `brainstorm`,
    `settings`, `syncer`, `stats-tui`, `diffviewer`).
  - **t848_4 (in-TUI editor modal):** Use
    `keybinding_registry._DEFAULTS` (or expose a public getter) to
    populate the editor's "current bindings for this scope" view. The
    map's key is `(scope, action_id)` and value is `(default_key, label)`.
    After the user edits a binding, call
    `shortcut_persist.save_override(scope, action_id, new_key)` and
    re-render the App's bindings.
  - **t848_5 (settings TUI shortcuts tab + export/import):** Persistence
    helpers already preserve sibling top-level keys (`email`,
    `last_used_labels`). Export/import flows can round-trip the
    `shortcuts:` subtree using PyYAML.
  - **t848_6 (docs):** SHARED_ACTION_IDS currently covers
    `quit`/`tui_switcher`/`refresh`/`shortcuts_editor`. Extend the
    `frozenset` literal when new cross-TUI actions land.
